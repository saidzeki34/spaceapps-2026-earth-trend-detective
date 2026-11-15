"""Where the interface gets its numbers.

Measured rivers come from the trend section (``mountain_water.trend``). This
file only reads its saved tables and calls its functions; it never changes
anything there.

Rivers without measurements get an imaginary record from ``imaginary.py``.
That record is pushed through the same trend calculations, so both kinds look
alike to the screens and differ only in the "imaginary" mark.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from mountain_water.ui import imaginary
from mountain_water.ui.controls import IMAGINARY_COLUMNS_OF_MEASURED_RIVERS

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = Path(__file__).resolve().parent / "web"
GEODATA_FILE = WEB_DIR / "data" / "geodata.json"

# The trend section currently covers Switzerland (CAMELS-CH).
MEASURED_COUNTRY = "CH"
# A calendar year is offered on the timeline when at least half of it has flow data.
MIN_FLOW_DAYS_FOR_A_YEAR = 183
HYDRO_YEAR_START_MONTH = 10
ALPHA = 0.05
MIN_YEARS_FOR_A_TREND = 15
# Catchment outlines are simplified to this tolerance (metres) for drawing only.
OUTLINE_TOLERANCE_M = 60.0

BUILD_HINT = (
    "No measured river data on this computer yet. From the repository root run "
    "`python -m mountain_water.trend download` and then `python -m mountain_water.trend build`."
)


@dataclass(frozen=True)
class River:
    id: str
    country: str
    name: str
    place: str  # where it is measured; empty for rivers without measurements
    measured: bool
    lat: float | None = None
    lon: float | None = None
    area_km2: float | None = None
    elevation_m: float | None = None


@dataclass
class RiverData:
    """Everything known about one river, real or imaginary."""

    river: River
    daily: pd.DataFrame  # one row per day: date, hydro_year, hydro_doy and the value columns
    annual: pd.DataFrame  # one row per hydrological year: the trend section's yearly metrics
    trends: pd.DataFrame  # one row per yearly metric: slope per decade, p-value, ...
    imaginary_columns: frozenset
    years: list[int]  # calendar years offered on the timeline
    source: str

    @property
    def prediction_year(self) -> int:
        return self.years[-1] + 1

    def is_imaginary(self, column: str) -> bool:
        return not self.river.measured or column in self.imaginary_columns


@dataclass
class _Tables:
    daily: dict[str, pd.DataFrame]  # river id -> its daily rows
    annual: pd.DataFrame
    trends: pd.DataFrame
    rivers: list[River]
    source: str


_locks_guard = threading.Lock()
_locks: dict = {}
_cache: dict = {}
_notes: dict[str, str] = {}


def _once(key, build):
    """Build a value the first time it is asked for; later calls reuse it.

    Each key has its own lock, so a slow build never holds up an unrelated one.
    """
    with _locks_guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        if key not in _cache:
            _cache[key] = build()
        return _cache[key]


def _tidy(text) -> str:
    return str(text).replace("_", " ").strip()


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


# ---------------------------------------------------------------------------
# Measured rivers: the trend section's saved results
# ---------------------------------------------------------------------------


def _outlet_positions(attrs: pd.DataFrame) -> dict[str, tuple[float | None, float | None]]:
    """Latitude and longitude of each measuring point, as exact as the dataset allows."""
    positions = {
        row.gauge_id: (_number(getattr(row, "lat", None)), _number(getattr(row, "lon", None)))
        for row in attrs.itertuples()
    }
    if not {"gauge_easting", "gauge_northing"} <= set(attrs.columns):
        return positions
    try:  # Swiss grid coordinates are more exact than the rounded lat/lon columns.
        from pyproj import Transformer

        to_wgs = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
        lon, lat = to_wgs.transform(
            attrs["gauge_easting"].to_numpy(dtype=float), attrs["gauge_northing"].to_numpy(dtype=float)
        )
    except Exception:  # noqa: BLE001 - the rounded positions are good enough to continue
        return positions
    for gauge_id, la, lo in zip(attrs["gauge_id"], lat, lon):
        if np.isfinite(la) and np.isfinite(lo):
            positions[gauge_id] = (round(float(la), 5), round(float(lo), 5))
    return positions


def _load_measured() -> _Tables | None:
    try:
        from mountain_water.trend import drivers, pipeline, trends
        from mountain_water.trend.settings import TrendSettings
    except Exception as error:  # noqa: BLE001 - report any import problem to the screen instead of crashing
        _notes["measured"] = f"The trend section could not be loaded ({error}). Install the project's dependencies."
        return None
    try:
        results = pipeline.load(REPO_ROOT / TrendSettings().processed_dir)
    except FileNotFoundError:
        _notes["measured"] = BUILD_HINT
        return None

    prefix = MEASURED_COUNTRY.lower() + "-"
    attrs = results.attributes[results.attributes["gauge_id"].isin(results.gauges)].copy()
    if "country" in attrs:  # the dataset also holds a few catchments just across the border
        attrs = attrs[attrs["country"].astype(str).str.upper() == MEASURED_COUNTRY]
    positions = _outlet_positions(attrs)
    rivers = [
        River(
            id=prefix + row.gauge_id,
            country=MEASURED_COUNTRY,
            name=_tidy(getattr(row, "water_body", row.gauge_id)),
            place=_tidy(getattr(row, "name", "")),
            measured=True,
            lat=positions[row.gauge_id][0],
            lon=positions[row.gauge_id][1],
            area_km2=_number(getattr(row, "area", None)),
            elevation_m=_number(getattr(row, "elevation", None)),
        )
        for row in attrs.itertuples()
    ]
    rivers.sort(key=lambda r: (r.name.lower(), r.place.lower()))
    keep = set(attrs["gauge_id"])

    daily = results.daily[results.daily["gauge_id"].isin(keep)].copy()
    daily["gauge_id"] = prefix + daily["gauge_id"]
    daily["evap"] = imaginary.evaporation(daily)  # imaginary: no evaporation source yet

    annual = results.annual[results.annual["gauge_id"].isin(keep)].copy()
    annual["gauge_id"] = prefix + annual["gauge_id"]
    trend_rows = results.trends[results.trends["gauge_id"].isin(keep)].copy()
    trend_rows["gauge_id"] = prefix + trend_rows["gauge_id"]
    if "evap_total_mm" not in annual:
        keys = ["gauge_id", "hydro_year"]
        evap_year = drivers.annual_driver_metrics(daily[[*keys, "date", "evap"]])
        annual = annual.merge(evap_year[[*keys, "evap_total_mm"]], on=keys, how="left")
        extra = trends.trend_table(annual, ["evap_total_mm"], ALPHA, min_years=MIN_YEARS_FOR_A_TREND)
        trend_rows = pd.concat([trend_rows, extra], ignore_index=True)

    provenance = results.meta.get("provenance") or {}
    version = provenance.get("version")
    source = "CAMELS-CH" + (f" v{version}" if version else "")
    return _Tables(dict(tuple(daily.groupby("gauge_id", sort=False))), annual, trend_rows, rivers, source)


def _measured() -> _Tables | None:
    return _once("measured", _load_measured)


# ---------------------------------------------------------------------------
# Rivers without measurements: an imaginary record through the same calculations
# ---------------------------------------------------------------------------


def _geodata() -> dict:
    return _once("geodata", lambda: json.loads(GEODATA_FILE.read_text(encoding="utf-8")))


def _major_rivers() -> list[River]:
    """The large rivers drawn on the map (Natural Earth). None of them has data connected yet."""
    return [
        River(id=f"{code.lower()}-{entry['id']}", country=code, name=entry["name"], place="", measured=False)
        for code, entries in _geodata()["rivers"].items()
        for entry in entries
    ]


def _load_imaginary(river: River) -> _Tables:
    """One river's imaginary record, analysed with the trend section's own functions."""
    from mountain_water.trend import drivers, preprocessing, trends
    from mountain_water.trend.flow_metrics import annual_volume_metrics
    from mountain_water.trend.registry import METRICS
    from mountain_water.trend.timing import annual_timing_metrics
    from mountain_water.trend.variability import annual_variability_metrics

    daily = imaginary.make_daily([river.id])
    daily = preprocessing.add_hydro_year(daily, HYDRO_YEAR_START_MONTH)
    # Keep whole hydrological years only, as the trend section does.
    days = daily.groupby("hydro_year")["date"].nunique()
    daily = daily[daily["hydro_year"].isin(days[days >= 365].index)]

    keys = ["gauge_id", "hydro_year"]
    annual = (
        annual_volume_metrics(daily)
        .merge(annual_timing_metrics(daily), on=keys, how="left")
        .merge(annual_variability_metrics(daily), on=keys, how="left")
        .merge(drivers.annual_driver_metrics(daily), on=keys, how="left")
    )
    annual["runoff_ratio"] = annual["runoff_mm"] / annual["precip_total_mm"]
    metrics = [m for m in METRICS if m in annual]
    trend_rows = trends.trend_table(annual, metrics, ALPHA, min_years=MIN_YEARS_FOR_A_TREND)
    return _Tables({river.id: daily}, annual, trend_rows, [river], "Imaginary record")


# ---------------------------------------------------------------------------
# What the rest of the interface uses
# ---------------------------------------------------------------------------


def countries() -> dict[str, str]:
    """Country code -> name, for the countries lit on the map."""
    return {code: entry["name"] for code, entry in _geodata()["countries"].items()}


def rivers() -> list[River]:
    """All rivers a person can pick: measured ones first, then the ones with imaginary data."""
    measured = _measured()
    return (measured.rivers if measured else []) + _major_rivers()


def find_river(river_id: str) -> River | None:
    return next((r for r in rivers() if r.id == river_id), None)


def river_data(river_id: str) -> RiverData:
    def build() -> RiverData:
        river = find_river(river_id)
        if river is None:
            raise KeyError(river_id)
        tables = _measured() if river.measured else _load_imaginary(river)
        daily = tables.daily[river_id].sort_values("date").reset_index(drop=True)
        flow_days = daily.dropna(subset=["discharge_vol"])["date"].dt.year.value_counts()
        years = sorted(int(y) for y, n in flow_days.items() if n >= MIN_FLOW_DAYS_FOR_A_YEAR)
        return RiverData(
            river=river,
            daily=daily,
            annual=tables.annual[tables.annual["gauge_id"] == river_id].sort_values("hydro_year"),
            trends=tables.trends[tables.trends["gauge_id"] == river_id],
            imaginary_columns=IMAGINARY_COLUMNS_OF_MEASURED_RIVERS if river.measured else frozenset(),
            years=years,
            source=tables.source,
        )

    return _once(("river", river_id), build)


def all_measured() -> _Tables | None:
    """The measured rivers' tables together, for views that compare rivers."""
    return _measured()


def status() -> dict:
    """Plain facts about what data is connected, for the 'About the data' note."""
    measured = _measured()
    return {
        "measured_rivers": len(measured.rivers) if measured else 0,
        "measured_source": measured.source if measured else None,
        "message": "" if measured else _notes.get("measured", BUILD_HINT),
    }


def catchment_outlines() -> dict[str, list[list[list[float]]]]:
    """River id -> simplified outline rings ([lat, lon] points) of its upstream catchment.

    Read from the catchment file that ships with the trend section's dataset.
    For drawing on the map only. Empty when the file or a library is missing.
    """

    def build() -> dict:
        measured = _measured()
        if measured is None:
            return {}
        try:
            import shapefile  # pyshp
            from pyproj import CRS, Transformer
            from shapely.geometry import shape
            from shapely.validation import make_valid

            from mountain_water.trend import camels_ch
            from mountain_water.trend.catchment_grid import CATCHMENT_SHAPEFILE
            from mountain_water.trend.settings import TrendSettings

            path = camels_ch.find_dataset_root(REPO_ROOT / TrendSettings().raw_dir) / CATCHMENT_SHAPEFILE
            reader = shapefile.Reader(str(path))
            prj = path.with_suffix(".prj")
            crs = CRS.from_wkt(prj.read_text()) if prj.exists() else CRS.from_epsg(2056)
            to_wgs = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        except Exception:  # noqa: BLE001 - the map still works with measuring points only
            return {}

        wanted = {river.id.split("-", 1)[1]: river.id for river in measured.rivers}
        outlines: dict[str, list] = {}
        for index, record in enumerate(reader.iterRecords()):
            raw = record.as_dict().get("gauge_id")
            gauge = str(int(raw)) if isinstance(raw, float) and raw.is_integer() else str(raw)
            if gauge not in wanted:
                continue
            geometry = reader.shape(index)  # read only the outlines that are needed
            polygon = make_valid(shape(geometry.__geo_interface__)).simplify(OUTLINE_TOLERANCE_M)
            rings = []
            for part in getattr(polygon, "geoms", [polygon]):
                if part.geom_type != "Polygon":
                    continue
                xs, ys = part.exterior.coords.xy
                lon, lat = to_wgs.transform(np.asarray(xs), np.asarray(ys))
                rings.append([[round(float(a), 5), round(float(b), 5)] for a, b in zip(lat, lon)])
            if rings:
                outlines[wanted[gauge]] = rings
        return outlines

    return _once("outlines", build)


def warm_up() -> None:
    """Load the measured data once so the first click does not wait. Safe to run in the background."""
    _measured()
    catchment_outlines()
