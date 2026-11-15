"""Norway: NVE observed daily discharge, catchment outlines and seNorge catchment meteorology.

Sources (NLOD licence; credit NVE / MET Norway):
    * HydAPI (https://hydapi.nve.no, free API key in ``NVE_API_KEY``): station metadata and daily
      mean discharge (parameter 1001, resolution 1440 min).
    * NVE map service HydrologiskeData3, layer "Totalnedbørfelt til målestasjon" (catchment
      upstream of each gauging station), EPSG:25833.
    * NVE GridTimeSeries (GTS, https://gts.nve.no/api, no key): seNorge 1 km daily precipitation
      (rr), mean temperature (tm) and snow water equivalent, averaged over each catchment polygon.

Everything downloaded is cached under ``data/raw/nve/`` so reruns only fetch what is missing.
Field names that could not be verified offline are tried from candidate lists; run
``python -m mountain_water.trend inspect --source nve`` to see the real ones.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

HYDAPI = "https://hydapi.nve.no/api/v1"
CATCHMENT_LAYER = "https://kart.nve.no/enterprise/rest/services/HydrologiskeData3/MapServer/38/query"
GTS = "https://gts.nve.no/api"
CRS = "EPSG:25833"
DEFAULT_RAW_DIR = Path("data/raw/nve")
START = "1960-10-01"  # first full hydrological year (Oct-Sep) is 1961
DISCHARGE = 1001
DAILY = 1440

# seNorge themes: theme code -> (column, unit). Theme codes per GTS /GridTimeSeries/Themes.
THEMES = {"rr": ("precipitation", "mm/d"), "tm": ("temperature_mean", "degC"), "swe": ("swe", "mm")}

# Station metadata: standard column -> candidate HydAPI field names (first present wins).
STATION_FIELDS = {
    "gauge_id": ("stationId",),
    "name": ("stationName",),
    "water_body": ("riverName",),
    "lat": ("latitude",),
    "lon": ("longitude",),
    "area": ("drainageBasinArea", "drainageBasinAreaNorway"),
    "elevation": ("heightHypso50", "heightHypsoMedian", "medianHeight"),
    "elevation_max": ("heightMaximum",),
    "glacier": ("percentGlacier",),
    "lake": ("percentEffLake", "percentLake"),
}
# Regulation: NVE's category ``catchmentRegTypeName`` decides ("uregulert" = unregulated, anything
# containing "regulert" = regulated, e.g. "regulert m/magasinregulering"). Only when it is empty do the
# numeric fields count: any of these > 0 marks a station as regulated.
REGULATION_TYPE_FIELD = "catchmentRegTypeName"
REGULATION_FIELDS = (
    "regulationArea", "regulationPartReservoirs", "reservoirAreaIn", "reservoirAreaOut", "reservoirVolumeIn",
    "reservoirVolumeOut", "transferAreaIn", "transferAreaOut", "volumeReservoirs", "numberReservoirs",
    "areaReservoirs",
)
# Catchment layer id fields (matched case-insensitively; the best-matching one is used).
POLYGON_ID_FIELDS = ("stasjonnr", "compoundkey12", "stasjon_nr", "compound_k", "stationid")


def default_end() -> str:
    """End of the last complete hydrological year (30 September)."""
    today = date.today()
    year = today.year if today.month >= 10 else today.year - 1
    return f"{year}-09-30"


# --------------------------------------------------------------------------- HTTP clients


def get_api_key() -> str:
    key = os.environ.get("NVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No NVE HydAPI key. Register for a free key at https://hydapi.nve.no/Users and run\n"
            "  export NVE_API_KEY=<key>\nbefore downloading NVE data."
        )
    return key


class NveClient:
    """Thin wrapper for HydAPI (needs key), the ArcGIS catchment layer and GTS (both open)."""

    def __init__(self, api_key: str | None, timeout: int = 300, retries: int = 3):
        import requests

        self.session = requests.Session()
        self.session.headers["accept"] = "application/json"
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries

    def _request(self, method: str, url: str, **kw):
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.request(method, url, timeout=self.timeout, **kw)
                if r.status_code in (401, 403):
                    raise PermissionError(f"{url}: HTTP {r.status_code} (check NVE_API_KEY)")
                r.raise_for_status()
                return r.json()
            except PermissionError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry network/server errors
                if attempt == self.retries:
                    raise
                log.info("Retry %d for %s: %s", attempt, url, exc)
                time.sleep(5 * attempt)
        raise AssertionError("unreachable")

    def hydapi(self, path: str, **params) -> dict:
        if not self.api_key:
            raise RuntimeError("HydAPI requests need NVE_API_KEY")
        return self._request("GET", f"{HYDAPI}/{path}", params=params, headers={"X-API-Key": self.api_key})

    def stations(self) -> list[dict]:
        return self.hydapi("Stations")["data"]

    def discharge(self, station_id: str, start: str, end: str) -> dict:
        return self.hydapi("Observations", StationId=station_id, Parameter=DISCHARGE, ResolutionTime=DAILY,
                           ReferenceTime=f"{start}/{end}")

    def catchment_page(self, offset: int, page_size: int = 1000) -> dict:
        params = dict(where="1=1", outFields="*", outSR=25833, f="geojson",
                      resultOffset=offset, resultRecordCount=page_size)
        return self._request("GET", CATCHMENT_LAYER, params=params)

    def catchment_fields(self) -> dict:
        return self._request("GET", CATCHMENT_LAYER, params=dict(where="1=1", outFields="*", resultRecordCount=1,
                                                                 f="json", returnGeometry="false"))

    def senorge(self, theme: str, rings: list, start: str, end: str) -> dict:
        body = {
            "Theme": theme, "StartDate": start, "EndDate": end, "Format": "json",
            "Rings": json.dumps({"rings": rings, "spatialReference": {"wkid": 25833}}),
        }
        return self._request("POST", f"{GTS}/AggregationTimeSeries/ByGeoJson", json=body)

    def themes(self):
        return self._request("GET", f"{GTS}/GridTimeSeries/Themes/json")


# --------------------------------------------------------------------------- station metadata


def _first(record: dict, candidates: tuple[str, ...]):
    for c in candidates:
        if c in record and record[c] is not None:
            return record[c]
    return None


def _daily_discharge_period(record: dict) -> tuple[str | None, str | None]:
    """dataFromTime/dataToTime of the daily (1440) discharge series, if listed in seriesList."""
    for series in record.get("seriesList") or []:
        if series.get("parameter") != DISCHARGE:
            continue
        for res in series.get("resolutionList") or []:
            if res.get("resTime") == DAILY:
                return res.get("dataFromTime"), res.get("dataToTime")
        return series.get("serieFrom"), series.get("serieTo")
    return None, None


def station_attributes(stations: list[dict]) -> pd.DataFrame:
    """One row per station: standard columns (gauge_id, name, lat, lon, area, elevation, glacier,
    regulated, q_first_year, q_last_year) plus every scalar HydAPI field as-is."""
    rows = []
    for rec in stations:
        row = {k: v for k, v in rec.items() if not isinstance(v, (list, dict))}
        for col, cands in STATION_FIELDS.items():
            row[col] = _first(rec, cands)
        row["regulated"], row["regulation_basis"] = _regulated(rec)
        q_from, q_to = _daily_discharge_period(rec)
        row["q_first_year"] = pd.Timestamp(q_from).year if q_from else np.nan
        row["q_last_year"] = pd.Timestamp(q_to).year if q_to else date.today().year
        row["has_daily_discharge"] = q_from is not None
        rows.append(row)
    out = pd.DataFrame(rows)
    out["gauge_id"] = out["gauge_id"].astype(str)
    for col in ("lat", "lon", "area", "elevation", "elevation_max", "glacier", "lake"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _regulated(rec: dict) -> tuple[int, str]:
    reg_type = str(rec.get(REGULATION_TYPE_FIELD) or "").strip().lower()
    if "uregul" in reg_type:
        return 0, reg_type
    if "regul" in reg_type:
        return 1, reg_type
    found = [f for f in REGULATION_FIELDS if rec.get(f) is not None]
    values = pd.to_numeric(pd.Series([rec.get(f) for f in found], dtype="object"), errors="coerce").fillna(0)
    hits = [f for f, v in zip(found, values) if v > 0]
    # No category and no positive field: treated as unregulated ("none recorded").
    return int(bool(hits)), "fields: " + ",".join(hits) if hits else "none recorded"


def candidate_stations(attrs: pd.DataFrame, min_elevation: float | None, max_area: float | None,
                       min_years: int, start: str, end: str) -> pd.DataFrame:
    """Pre-filter on metadata so only plausible mountain stations are downloaded."""
    span_start, span_end = pd.Timestamp(start).year, pd.Timestamp(end).year
    keep = attrs["has_daily_discharge"].astype(bool) & (attrs["regulated"] == 0)
    if min_elevation is not None:
        keep &= attrs["elevation"] >= min_elevation
    if max_area is not None:
        keep &= attrs["area"] <= max_area
    first = attrs["q_first_year"].fillna(span_end).clip(lower=span_start)
    last = attrs["q_last_year"].fillna(span_end).clip(upper=span_end)
    keep &= (last - first + 1) >= min_years
    return attrs[keep]


# --------------------------------------------------------------------------- catchment polygons


def station_key(value, area_no=None) -> tuple[int, int] | None:
    """(watercourse area, station) from any id form: "2.11.0", "2.11", "002.00011.000" -> (2, 11).

    A lone station number is combined with the watercourse area number when one is given.
    """
    if value is None:
        return None
    ints = [int(x) for x in re.findall(r"\d+", str(value))]
    if len(ints) >= 2:
        return ints[0], ints[1]
    if len(ints) == 1 and area_no is not None:
        area = re.findall(r"\d+", str(area_no))
        return (int(area[0]), ints[0]) if area else None
    return None


def catchment_polygons(geojson: dict, gauge_ids: list[str] | None = None) -> tuple[dict, str]:
    """{gauge_id: shapely geometry (EPSG:25833)}, matching HydAPI ids to the layer's station number on
    (watercourse area, station), ignoring the version suffix and zero padding."""
    from shapely.geometry import shape
    from shapely.validation import make_valid

    features = [f for f in geojson.get("features", []) if f.get("geometry")]
    if not features:
        return {}, CRS
    lower = {k.lower(): k for k in features[0].get("properties", {})}
    id_fields = [lower[c] for c in POLYGON_ID_FIELDS if c in lower]
    if not id_fields:
        raise KeyError(f"No station id field in catchment layer; fields: {sorted(lower.values())}")
    area_field = lower.get("vassdragsomradenr")
    wanted = {gid: station_key(gid) for gid in (gauge_ids or [])}

    def index(field):
        by_key: dict[tuple, object] = {}
        for f in features:
            props = f["properties"]
            key = station_key(props.get(field), props.get(area_field) if area_field else None)
            if key is None:
                continue
            geom = make_valid(shape(f["geometry"]))
            if key not in by_key or geom.area > by_key[key].area:
                by_key[key] = geom
        return by_key

    # Use the id field that matches the most requested stations.
    indexed = [index(f) for f in id_fields]
    best = max(indexed, key=lambda ix: sum(k in ix for k in wanted.values())) if wanted else indexed[0]
    if gauge_ids is None:
        return {f"{a}.{b}.0": g for (a, b), g in best.items()}, CRS
    return {gid: best[key] for gid, key in wanted.items() if key in best}, CRS


def rings(geom, tolerance: float = 50.0) -> list:
    """ArcGIS-style rings (exterior rings, metres) of a simplified polygon for the GTS API."""
    g = geom.simplify(tolerance, preserve_topology=True)
    parts = getattr(g, "geoms", [g])
    return [[[round(x), round(y)] for x, y in p.exterior.coords] for p in parts if p.geom_type == "Polygon"]


# --------------------------------------------------------------------------- parsing


def parse_discharge(payload: dict) -> pd.DataFrame:
    """HydAPI Observations JSON -> date, discharge_vol (m³/s), quality. Dates in Norwegian local time."""
    data = payload.get("data") or []
    if not data:
        return pd.DataFrame(columns=["date", "discharge_vol", "quality"])
    obs = pd.DataFrame(data[0].get("observations") or [])
    if obs.empty:
        return pd.DataFrame(columns=["date", "discharge_vol", "quality"])
    t = pd.to_datetime(obs["time"], utc=True).dt.tz_convert("Europe/Oslo").dt.tz_localize(None).dt.normalize()
    out = pd.DataFrame({
        "date": t,
        "discharge_vol": pd.to_numeric(obs["value"], errors="coerce"),
        "quality": pd.to_numeric(obs.get("quality"), errors="coerce"),
    })
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def parse_senorge(payload: dict, start: str) -> pd.Series:
    """GTS aggregated response -> daily series starting at ``start``; NoDataValue becomes NaN."""
    if "Data" in payload:
        values = np.asarray(payload["Data"], dtype=float)
    elif payload.get("CellTimeSeries"):  # per-cell response: average over cells
        values = np.nanmean([np.asarray(c["Data"], dtype=float) for c in payload["CellTimeSeries"]], axis=0)
    else:
        raise ValueError(f"Unexpected GTS response keys: {sorted(payload)}")
    if payload.get("TimeResolution", DAILY) != DAILY:
        raise ValueError(f"Expected daily GTS data, got TimeResolution={payload.get('TimeResolution')}")
    nodata = payload.get("NoDataValue")
    if nodata is not None:
        values[values == float(nodata)] = np.nan
    index = pd.date_range(pd.Timestamp(start), periods=len(values), freq="D", name="date")
    return pd.Series(values, index=index)


# --------------------------------------------------------------------------- download + load


def _chunks(start: str, end: str, years: int) -> list[tuple[str, str]]:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    while s <= e:
        stop = min(s + pd.DateOffset(years=years) - pd.Timedelta(days=1), e)
        out.append((s.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d")))
        s = stop + pd.Timedelta(days=1)
    return out


def load_stations(raw_dir: Path) -> pd.DataFrame:
    path = raw_dir / "stations.json"
    if not path.exists():
        raise FileNotFoundError(f"No NVE station list in {raw_dir}. Run `download --source nve` first.")
    return station_attributes(json.loads(path.read_text()))


def load_catchments(raw_dir: Path, gauge_ids: list[str] | None = None) -> tuple[dict, str]:
    path = raw_dir / "catchments.geojson"
    if not path.exists():
        raise FileNotFoundError(f"No NVE catchment outlines in {raw_dir}. Run `download --source nve` first.")
    return catchment_polygons(json.loads(path.read_text()), gauge_ids)


def download(
    raw_dir: Path = DEFAULT_RAW_DIR,
    start: str = START,
    end: str | None = None,
    min_elevation: float | None = 800.0,
    max_area: float | None = 500.0,
    min_years: int = 30,
    chunk_years: int = 20,
    workers: int = 3,
    client: NveClient | None = None,
    themes: dict = THEMES,
) -> pd.DataFrame:
    """Station list, catchment outlines, then discharge and seNorge series for candidate stations."""
    end = end or default_end()
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = client or NveClient(get_api_key())

    st_path = raw_dir / "stations.json"
    if not st_path.exists():
        st_path.write_text(json.dumps(client.stations()))
    attrs = load_stations(raw_dir)
    cands = candidate_stations(attrs, min_elevation, max_area, min_years, start, end)
    log.info("%d stations, %d mountain candidates", len(attrs), len(cands))

    poly_path = raw_dir / "catchments.geojson"
    if not poly_path.exists():
        features, offset = [], 0
        while True:
            page = client.catchment_page(offset)
            feats = page.get("features", [])
            features += feats
            more = page.get("exceededTransferLimit") or page.get("properties", {}).get("exceededTransferLimit")
            if not feats or (not more and len(feats) < 1000):
                break
            offset += len(feats)
        poly_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    polygons, _ = load_catchments(raw_dir, list(cands["gauge_id"]))
    log.info("Catchment outlines found for %d of %d candidates", len(polygons), len(cands))

    tasks = [("discharge", gid, None, start, end) for gid in cands["gauge_id"]]
    tasks += [("senorge", gid, theme, s, e) for gid in polygons for theme in themes
              for s, e in _chunks(start, end, chunk_years)]

    def path_for(kind, gid, theme, s, e):
        if kind == "discharge":
            return raw_dir / "discharge" / f"{gid}.json"
        return raw_dir / "senorge" / gid / f"{theme}_{s}_{e}.json"

    def run(task):
        kind, gid, theme, s, e = task
        payload = client.discharge(gid, s, e) if kind == "discharge" else client.senorge(theme, rings(polygons[gid]), s, e)
        n = len(parse_discharge(payload)) if kind == "discharge" else len(parse_senorge(payload, s))
        path = path_for(*task)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        return n

    todo = [t for t in tasks if not path_for(*t).exists()]
    log.info("%d requests, %d cached, %d to fetch", len(tasks), len(tasks) - len(todo), len(todo))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, t): t for t in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            kind, gid, theme, s, e = futures[fut]
            try:
                n, err = fut.result(), ""
            except PermissionError:
                pool.shutdown(cancel_futures=True)
                raise
            except Exception as exc:  # noqa: BLE001 - record and continue
                n, err = 0, str(exc)[:200]
                log.warning("Failed %s %s %s %s..%s: %s", kind, gid, theme or "", s, e, err)
            results.append(dict(kind=kind, gauge_id=gid, theme=theme or "", start=s, end=e, values=n, error=err))
            if i % 25 == 0 or i == len(todo):
                log.info("%d/%d requests done", i, len(todo))
    return pd.DataFrame(results, columns=["kind", "gauge_id", "theme", "start", "end", "values", "error"])


def load_daily(raw_dir: Path, attrs: pd.DataFrame, themes: dict = THEMES) -> tuple[pd.DataFrame, dict]:
    """Daily table in the CAMELS-CH layout: gauge_id, date, discharge_vol, discharge_spec, quality,
    precipitation, temperature_mean, swe (only stations with downloaded discharge)."""
    area = attrs.set_index("gauge_id")["area"]
    frames = []
    for path in sorted((raw_dir / "discharge").glob("*.json")):
        gid = path.stem
        q = parse_discharge(json.loads(path.read_text()))
        if q.empty:
            continue
        q = q.set_index("date")
        for theme, (col, _) in themes.items():
            parts = [parse_senorge(json.loads(p.read_text()), p.stem.split("_")[1])
                     for p in sorted((raw_dir / "senorge" / gid).glob(f"{theme}_*.json"))]
            if parts:
                s = pd.concat(parts)
                q[col] = s[~s.index.duplicated()].reindex(q.index)
        q = q.reset_index()
        q.insert(0, "gauge_id", gid)
        q["discharge_spec"] = q["discharge_vol"] * 86.4 / area.get(gid, np.nan)
        frames.append(q)
    if not frames:
        raise FileNotFoundError(f"No NVE discharge cached under {raw_dir}. Run `download --source nve` first.")
    daily = pd.concat(frames, ignore_index=True)
    units = {"discharge_vol": "m3/s", "discharge_spec": "mm/d"} | {c: u for c, u in themes.values()}
    return daily, units


def describe(client: NveClient) -> str:
    """Show real field names of the three services, to check the candidate lists above."""
    lines = []
    try:
        stations = client.stations()
        sample = next((s for s in stations if _daily_discharge_period(s)[0]), stations[0])
        lines.append(f"HydAPI: {len(stations)} stations. Fields of {sample.get('stationId')}:")
        lines += [f"  {k} = {v!r}"[:160] for k, v in sample.items() if k != "seriesList"]
        lines.append(f"  seriesList[0] = {json.dumps((sample.get('seriesList') or [None])[0])[:400]}")
        found = {c: _first(sample, cands) is not None for c, cands in STATION_FIELDS.items()}
        lines.append(f"  standard fields found: {found}")
        lines.append(f"  regulation fields present: {[f for f in REGULATION_FIELDS if f in sample]}")
        attrs = station_attributes(stations)
        lines.append("  regulation categories: " + attrs["regulation_basis"].value_counts().head(8).to_string().replace("\n", "; "))
    except Exception as exc:  # noqa: BLE001 - show what works even if one service fails
        lines.append(f"HydAPI failed: {exc}")
    try:
        layer = client.catchment_fields()
        fields = [f.get("name") for f in layer.get("fields", [])]
        example = (layer.get("features") or [{}])[0].get("attributes", {})
        lines.append(f"Catchment layer fields: {fields}")
        lines.append(f"  example: {json.dumps(example, ensure_ascii=False)[:600]}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"Catchment layer failed: {exc}")
    try:
        themes = {t.get("Name"): t for t in client.themes()}
        lines.append(f"GTS themes ({len(themes)}): {', '.join(sorted(themes))}")
        for name in THEMES:
            t = themes.get(name)
            lines.append(f"  {name}: " + (f"{t.get('Fullname')}, {t.get('HumanReadableUnit')}, "
                                         f"{t.get('TimeResolutionInMinutes')} min, from {t.get('FirstDateInTimeSerie')}"
                                         if t else "MISSING"))
    except Exception as exc:  # noqa: BLE001
        lines.append(f"GTS themes failed: {exc}")
    return "\n".join(lines)
