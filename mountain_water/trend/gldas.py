"""GLDAS-2.1 Noah (0.25°, 3-hourly) point time series via the NASA Giovanni Time Series API.

Product: GLDAS_NOAH025_3H 2.1 (Beaudoing & Rodell, NASA GES DISC), 2000-01-01 to ~3 months ago.
Access: https://api.giovanni.earthdata.nasa.gov/timeseries with an Earthdata Login bearer token
(set ``EARTHDATA_TOKEN``; create one at https://urs.earthdata.nasa.gov -> Generate Token, valid 60 days).

GLDAS is a land-surface *model*. Its runoff (surface + baseflow) is not routed through a river
network, so it is not the same as discharge at a gauge, especially for timing.

Raw API responses are cached under ``data/raw/gldas/`` so interrupted downloads resume and
parsing can be changed without downloading again.
"""

from __future__ import annotations

import io
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .catchment_grid import CATCHMENT_SHAPEFILE, cell_weights, weighted_mean

log = logging.getLogger(__name__)

API_URL = "https://api.giovanni.earthdata.nasa.gov/timeseries"
COLLECTION = "GLDAS_NOAH025_3H_2_1"
DEFAULT_RAW_DIR = Path("data/raw/gldas")
START = "2000-01-01"
STEP_SECONDS = 3 * 3600
FILL_VALUE = -9999.0


@dataclass(frozen=True)
class Variable:
    name: str      # GLDAS short name
    column: str    # column in the daily table (same names as CAMELS-CH where the meaning matches)
    kind: str      # 'acc' (kg m-2 per 3 h), 'rate' (kg m-2 s-1), 'kelvin', 'state' (kg m-2)
    unit: str      # unit after conversion to daily values


VARIABLES = [
    Variable("Qs_acc", "runoff_surface", "acc", "mm/d"),
    Variable("Qsb_acc", "runoff_base", "acc", "mm/d"),
    Variable("Qsm_acc", "snowmelt", "acc", "mm/d"),
    Variable("Rainf_f_tavg", "precipitation", "rate", "mm/d"),
    Variable("Snowf_tavg", "snowfall", "rate", "mm/d"),
    Variable("Evap_tavg", "evap", "rate", "mm/d"),
    Variable("Tair_f_inst", "temperature_mean", "kelvin", "degC"),
    Variable("SWE_inst", "swe", "state", "mm"),
]


# --------------------------------------------------------------------------- API client


def get_token() -> str:
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if token:
        return token
    try:  # optional: reuse an earthaccess login (~/.netrc) if the package is installed
        import earthaccess

        earthaccess.login(strategy="netrc")
        return earthaccess.get_edl_token()["access_token"]
    except Exception:  # noqa: BLE001 - any failure means no usable credentials
        pass
    raise RuntimeError(
        "No Earthdata token. Create one at https://urs.earthdata.nasa.gov (Generate Token) and run\n"
        "  export EARTHDATA_TOKEN=<token>\nbefore downloading GLDAS."
    )


class GiovanniClient:
    def __init__(self, token: str, timeout: int = 300, retries: int = 3):
        import requests

        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.timeout = timeout
        self.retries = retries

    def fetch(self, variable: str, lat: float, lon: float, start: str, end: str) -> str:
        params = {
            "data": f"{COLLECTION}_{variable}",
            "location": f"[{lat:.4f},{lon:.4f}]",
            "time": f"{start}T00:00:00/{end}T23:59:59",
        }
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.get(API_URL, params=params, timeout=self.timeout)
                if r.status_code in (401, 403):
                    raise PermissionError(f"Earthdata token rejected (HTTP {r.status_code}); create a new token")
                r.raise_for_status()
                return r.text
            except PermissionError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry network/server errors
                if attempt == self.retries:
                    raise
                log.info("Retry %d for %s %s,%s: %s", attempt, variable, lat, lon, exc)
                time.sleep(5 * attempt)
        raise AssertionError("unreachable")


# --------------------------------------------------------------------------- parsing


_TIME_LINE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}[T ]\d{2}")


def parse_timeseries(text: str) -> tuple[pd.Series, dict[str, str]]:
    """Parse a Giovanni time-series CSV: ``key:,value`` header lines, then ``Timestamp (UTC),Data``.

    Tolerant of variations: everything before the first timestamped line is treated as metadata.
    Fill values (-9999) become NaN.
    """
    meta: dict[str, str] = {}
    data_lines = []
    for line in text.splitlines():
        if _TIME_LINE.match(line):
            data_lines.append(line)
        elif not data_lines and line.strip():
            key, _, value = line.partition(",")
            meta[key.strip().rstrip(":").strip()] = value.strip().strip('"')
    if not data_lines:
        raise ValueError("No timestamped rows in response: " + text[:300].replace("\n", " | "))
    body = "\n".join(data_lines).replace("\t", ",")
    df = pd.read_csv(io.StringIO(body), header=None, usecols=[0, 1], skipinitialspace=True, dtype={0: str})
    times = pd.to_datetime(df[0].str.strip().str.rstrip("Z"), format="ISO8601")
    values = pd.to_numeric(df[1], errors="coerce").where(lambda v: v > FILL_VALUE + 1)
    return pd.Series(values.to_numpy(), index=times, name="value"), meta


def to_daily(series: pd.Series, kind: str) -> pd.Series:
    """3-hourly values -> daily values in mm/d, mm or °C. Days with fewer than 8 values become NaN."""
    s = series.sort_index()
    s = s[~s.index.duplicated()]
    day = s.index.floor("D")
    g = s.groupby(day)
    n = g.count()
    if kind == "acc":  # kg m-2 accumulated over each 3-h step
        daily = g.sum()
    elif kind == "rate":  # kg m-2 s-1 averaged over each 3-h step
        daily = g.mean() * 86400
    elif kind == "kelvin":
        daily = g.mean() - 273.15
    else:  # state, e.g. SWE in kg m-2 = mm
        daily = g.mean()
    daily = daily.where(n >= 8)
    daily.index.name = "date"
    return daily


# --------------------------------------------------------------------------- download + load


def _chunks(start: str, end: str, years: int) -> list[tuple[str, str]]:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    while s <= e:
        stop = min(pd.Timestamp(year=s.year + years, month=1, day=1) - pd.Timedelta(days=1), e)
        out.append((s.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d")))
        s = stop + pd.Timedelta(days=1)
    return out


def default_end() -> str:
    """GLDAS-2.1 lags about 3 months; request up to the end of the month 4 months ago."""
    first = date.today().replace(day=1)
    for _ in range(3):
        first = (first - timedelta(days=1)).replace(day=1)
    return (first - timedelta(days=1)).isoformat()


def _cache_path(raw_dir: Path, lat: float, lon: float, variable: str, start: str, end: str) -> Path:
    return raw_dir / COLLECTION / f"{lat:.3f}_{lon:.3f}" / f"{variable}_{start}_{end}.csv"


def download(
    weights: pd.DataFrame,
    raw_dir: Path = DEFAULT_RAW_DIR,
    start: str = START,
    end: str | None = None,
    chunk_years: int = 5,
    workers: int = 4,
    client: GiovanniClient | None = None,
) -> pd.DataFrame:
    """Fetch every variable for every cell in ``weights``; returns a table of request outcomes."""
    end = end or default_end()
    cells = weights[["cell_lat", "cell_lon"]].drop_duplicates().itertuples(index=False)
    tasks = [
        (lat, lon, v.name, s, e)
        for lat, lon in cells for v in VARIABLES for s, e in _chunks(start, end, chunk_years)
    ]
    todo = [t for t in tasks if not _cache_path(raw_dir, *t[:3], *t[3:]).exists()]
    log.info("%d requests total, %d cached, %d to fetch", len(tasks), len(tasks) - len(todo), len(todo))
    client = client or GiovanniClient(get_token())

    def run(task):
        lat, lon, var, s, e = task
        text = client.fetch(var, lat, lon, s, e)
        series, _ = parse_timeseries(text)  # only cache responses that parse
        path = _cache_path(raw_dir, lat, lon, var, s, e)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return len(series)

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, t): t for t in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            lat, lon, var, s, e = futures[fut]
            try:
                n, err = fut.result(), ""
            except PermissionError:
                pool.shutdown(cancel_futures=True)
                raise
            except Exception as exc:  # noqa: BLE001 - record and continue with the other requests
                n, err = 0, str(exc)[:200]
                log.warning("Failed %s at %.3f,%.3f %s..%s: %s", var, lat, lon, s, e, err)
            results.append(dict(cell_lat=lat, cell_lon=lon, variable=var, start=s, end=e, values=n, error=err))
            if i % 50 == 0 or i == len(todo):
                log.info("%d/%d requests done", i, len(todo))
    return pd.DataFrame(results, columns=["cell_lat", "cell_lon", "variable", "start", "end", "values", "error"])


def load_cell_daily(raw_dir: Path, lat: float, lon: float) -> pd.DataFrame:
    """Daily table for one cell from all cached chunks (missing variables are simply absent)."""
    folder = raw_dir / COLLECTION / f"{lat:.3f}_{lon:.3f}"
    cols = {}
    for v in VARIABLES:
        parts = [parse_timeseries(p.read_text())[0] for p in sorted(folder.glob(f"{v.name}_*.csv"))]
        if parts:
            cols[v.column] = to_daily(pd.concat(parts), v.kind)
    if not cols:
        return pd.DataFrame(columns=["date"])
    out = pd.DataFrame(cols)
    out.index.name = "date"
    return out.reset_index().assign(cell_lat=lat, cell_lon=lon)


def load_daily(weights: pd.DataFrame, raw_dir: Path = DEFAULT_RAW_DIR) -> tuple[pd.DataFrame, dict[str, str]]:
    """Catchment-mean daily series in the same layout as the CAMELS-CH observed table.

    ``discharge_spec`` (mm/d) is total runoff = surface + baseflow runoff, and ``discharge_vol``
    is the equivalent flow in m³/s for the catchment area, so all flow metrics apply unchanged.
    """
    cells = weights[["cell_lat", "cell_lon"]].drop_duplicates().itertuples(index=False)
    frames = [load_cell_daily(raw_dir, lat, lon) for lat, lon in cells]
    frames = [f for f in frames if len(f)]
    if not frames:
        raise FileNotFoundError(f"No GLDAS data cached under {raw_dir}. Run `download --source gldas` first.")
    per_cell = pd.concat(frames, ignore_index=True)
    columns = [v.column for v in VARIABLES if v.column in per_cell]
    daily = weighted_mean(per_cell, weights, columns)
    if {"runoff_surface", "runoff_base"} <= set(daily.columns):
        daily["discharge_spec"] = daily["runoff_surface"] + daily["runoff_base"]
        area = daily["gauge_id"].map(weights.groupby("gauge_id")["catchment_area_km2"].first())
        daily["discharge_vol"] = daily["discharge_spec"] * area / 86.4
    daily["date"] = pd.to_datetime(daily["date"])
    units = {v.column: v.unit for v in VARIABLES} | {"discharge_spec": "mm/d", "discharge_vol": "m3/s"}
    return daily.sort_values(["gauge_id", "date"]).reset_index(drop=True), units


def catchment_weights(camels_root: Path, gauge_ids: list[str]) -> pd.DataFrame:
    return cell_weights(camels_root / CATCHMENT_SHAPEFILE, gauge_ids, resolution=0.25)


def probe(lat: float = 46.625, lon: float = 8.375, client: GiovanniClient | None = None) -> str:
    """One small request (two days of air temperature) to check the token and the response format."""
    client = client or GiovanniClient(get_token())
    text = client.fetch("Tair_f_inst", lat, lon, "2010-01-01", "2010-01-02")
    series, meta = parse_timeseries(text)
    head = "\n".join(text.splitlines()[:25])
    return f"{head}\n...\nParsed {len(series)} values, mean {np.nanmean(series):.2f} (K). Metadata keys: {list(meta)}"
