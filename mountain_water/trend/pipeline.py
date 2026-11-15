"""End-to-end trend pipeline: parse -> filter -> annual metrics -> trends, window comparison, drivers.

Usage from Python (e.g. Streamlit)::

    from mountain_water.trend import pipeline
    results = pipeline.load()          # cached tables from data/processed/trend
    results = pipeline.build()         # recompute from data/raw/camels_ch
    gldas = pipeline.build_gldas()     # same catchments from GLDAS-2.1 (data/raw/gldas)
    norway = pipeline.build_nve()      # NVE discharge + seNorge (data/raw/nve)
    no_gldas = pipeline.build_gldas(region="no")
    gldas = pipeline.load(TrendSettings.gldas().processed_dir)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from mountain_water.si import disclosure

from . import camels_ch, comparison, drivers, gldas, nve, preprocessing, seasonal, trends
from .catchment_grid import polygon_cell_weights
from .flow_metrics import annual_volume_metrics
from .registry import DRIVER_METRICS, FLOW_METRICS
from .settings import TrendSettings
from .timing import annual_timing_metrics
from .variability import annual_variability_metrics

log = logging.getLogger(__name__)

FLOW = "discharge_vol"
GAP_FILL_COLUMNS = ["discharge_vol", "discharge_spec"]
# Static attributes used to relate trends to catchment properties (first match per group is used).
ATTRIBUTE_CANDIDATES = {
    "elevation": ("elev_mean", "mean_elev"),
    "area": ("area", "area_km2"),
    "slope": ("slope_mean", "mean_slope"),
    "glacier": ("glac_area", "glac_frac", "glacier_fraction"),
}
LABEL_CANDIDATES = {
    "name": ("gauge_name", "name"),
    "water_body": ("water_body_name", "river"),
    "lat": ("gauge_lat", "lat", "latitude"),
    "lon": ("gauge_lon", "lon", "longitude"),
}

TABLES = (
    "attributes", "selection_log", "completeness", "daily", "annual", "trends", "window_comparison",
    "regime_monthly", "regime_daily", "correlations", "correlation_summary", "attribution",
    "trend_vs_attributes",
)


@dataclass
class TrendResults:
    attributes: pd.DataFrame
    selection_log: pd.DataFrame
    completeness: pd.DataFrame
    daily: pd.DataFrame
    annual: pd.DataFrame
    trends: pd.DataFrame
    window_comparison: pd.DataFrame
    regime_monthly: pd.DataFrame
    regime_daily: pd.DataFrame
    correlations: pd.DataFrame
    correlation_summary: pd.DataFrame
    attribution: pd.DataFrame
    trend_vs_attributes: pd.DataFrame
    meta: dict = field(default_factory=dict)

    @property
    def gauges(self) -> list[str]:
        return sorted(self.annual["gauge_id"].unique())

    def gauge_label(self, gauge_id: str) -> str:
        row = self.attributes.loc[self.attributes["gauge_id"] == gauge_id]
        if row.empty or "name" not in row:
            return gauge_id
        return f"{row['name'].iloc[0]} ({gauge_id})"

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in TABLES:
            getattr(self, name).to_parquet(directory / f"{name}.parquet", index=False)
        metadata = {**self.meta, "si_assistance": disclosure()}
        (directory / "meta.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def _standard_columns(attrs: pd.DataFrame) -> pd.DataFrame:
    """Add stable alias columns (name, lat, lon, elevation, ...) next to the original attribute names."""
    out = attrs.copy()
    for alias, candidates in {**LABEL_CANDIDATES, **ATTRIBUTE_CANDIDATES}.items():
        col = next((c for c in candidates if c in out.columns), None)
        if col is not None and alias not in out.columns:
            out[alias] = out[col]
    return out


def build(settings: TrendSettings | None = None, save: bool = True) -> TrendResults:
    """CAMELS-CH: observed daily series, mountain catchment filter, full analysis."""
    s = settings or TrendSettings()
    root = camels_ch.find_dataset_root(s.raw_dir)
    log.info("Reading CAMELS-CH from %s", root)

    attrs = _standard_columns(camels_ch.load_attributes(root))
    obs, units = camels_ch.load_observed(root)
    obs = _prepare(obs, s)
    completeness = preprocessing.year_completeness(obs, FLOW)
    gauges, selection_log = preprocessing.select_catchments(attrs, completeness, s.filters, s.min_year_completeness)
    meta = dict(source="camels_ch", flow_label="Discharge", dataset_root=str(root), provenance=_read_provenance(root))
    return analyze(obs, attrs, units, completeness, gauges, selection_log, s, meta, save)


def build_nve(settings: TrendSettings | None = None, save: bool = True) -> TrendResults:
    """Norway: NVE daily discharge + seNorge catchment meteorology, mountain filter, full analysis."""
    s = settings or TrendSettings.nve()
    stations = nve.load_stations(s.nve_raw_dir)
    attrs = stations[stations["has_daily_discharge"].astype(bool)].reset_index(drop=True)
    obs, units = nve.load_daily(s.nve_raw_dir, attrs)
    obs = _prepare(obs, s)
    completeness = preprocessing.year_completeness(obs, FLOW)
    gauges, selection_log = preprocessing.select_catchments(attrs, completeness, s.filters, s.min_year_completeness)
    selection_log.loc[0, "step"] = "NVE stations with daily discharge"
    selection_log["step"] = selection_log["step"].str.replace("reservoirs <= 0 [regulated]", "unregulated [regulated]",
                                                              regex=False)
    meta = dict(source="nve", flow_label="Discharge", dataset="NVE HydAPI daily discharge (1001) + seNorge via GTS",
                downloaded_stations=sorted(obs["gauge_id"].unique()))
    return analyze(obs, attrs, units, completeness, gauges, selection_log, s, meta, save)


def build_gldas(settings: TrendSettings | None = None, gauge_ids: list[str] | None = None,
                save: bool = True, region: str | None = None) -> TrendResults:
    """GLDAS-2.1 Noah runoff and drivers, area-weighted over the selected catchment outlines.

    ``region`` "ch" uses the CAMELS-CH catchments, "no" the NVE catchments. By default the
    catchments are the observed selection from the last ``build`` of that region.
    """
    region = region or (settings.region if settings else "ch")
    s = settings or TrendSettings.gldas(region)
    gauge_ids = gauge_ids or observed_selection(region)
    attrs, weights = gldas_inputs(region, gauge_ids, s)
    obs, units = gldas.load_daily(weights, s.gldas_raw_dir)
    obs = _prepare(obs, s)
    completeness = preprocessing.year_completeness(obs, FLOW)

    n_valid = preprocessing.valid_years(completeness, s.min_year_completeness).groupby("gauge_id").size()
    with_data = sorted(obs.loc[obs[FLOW].notna(), "gauge_id"].unique())
    gauges = [g for g in with_data if n_valid.get(g, 0) >= s.filters.min_valid_years]
    selection_log = pd.DataFrame([
        (f"{'NVE' if region == 'no' else 'CAMELS-CH'} mountain selection", len(gauge_ids)),
        ("Catchment outline and GLDAS runoff available", len(with_data)),
        (f">= {s.filters.min_valid_years} years with >= {s.min_year_completeness:.0%} valid days", len(gauges)),
    ], columns=["step", "remaining"])
    meta = dict(
        source="gldas", region=region, flow_label="GLDAS runoff",
        product=f"{gldas.COLLECTION} (GLDAS-2.1 Noah 0.25° 3-hourly)", cells=weights.to_dict(orient="records"),
    )
    return analyze(obs, attrs, units, completeness, gauges, selection_log, s, meta, save)


def gldas_inputs(region: str, gauge_ids: list[str], s: TrendSettings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(attributes, GLDAS cell weights) for the region's catchment outlines."""
    if region == "no":
        attrs = nve.load_stations(s.nve_raw_dir)
        polygons, crs = nve.load_catchments(s.nve_raw_dir, gauge_ids)
        return attrs, polygon_cell_weights(polygons, crs, resolution=0.25)
    root = camels_ch.find_dataset_root(s.raw_dir)
    return _standard_columns(camels_ch.load_attributes(root)), gldas.catchment_weights(root, gauge_ids)


def observed_selection(region: str = "ch") -> list[str]:
    """Selected gauges of the last observed build (CAMELS-CH for "ch", NVE for "no")."""
    meta_path = TrendSettings.observed(region).processed_dir / "meta.json"
    if not meta_path.exists():
        cmd = "build --source nve" if region == "no" else "build"
        raise FileNotFoundError(f"No observed selection for region '{region}' yet. Run `python -m mountain_water.trend {cmd}` first.")
    return list(json.loads(meta_path.read_text())["selected_gauges"])


def camels_selection(processed_dir: Path | None = None) -> list[str]:
    return observed_selection("ch") if processed_dir is None else \
        list(json.loads((processed_dir / "meta.json").read_text())["selected_gauges"])


def _prepare(obs: pd.DataFrame, s: TrendSettings) -> pd.DataFrame:
    obs = preprocessing.add_hydro_year(obs, s.hydro_year_start_month)
    return preprocessing.fill_short_gaps(obs, GAP_FILL_COLUMNS, s.max_gap_fill_days)


def analyze(obs: pd.DataFrame, attrs: pd.DataFrame, units: dict, completeness: pd.DataFrame, gauges: list[str],
            selection_log: pd.DataFrame, s: TrendSettings, meta: dict, save: bool = True) -> TrendResults:
    """Source-independent analysis of a prepared daily table (gauge_id, date, hydro_year, discharge_vol, ...)."""
    log.info("Selected %d catchments", len(gauges))
    if not gauges:
        raise ValueError(f"No catchments left after filtering:\n{selection_log.to_string(index=False)}")

    ok_years = preprocessing.valid_years(completeness, s.min_year_completeness)
    ok_years = ok_years[ok_years["gauge_id"].isin(gauges)]
    daily = obs.merge(ok_years, on=["gauge_id", "hydro_year"], how="inner")

    wins = preprocessing.windows(ok_years["hydro_year"].unique(), s.window_years, s.min_window_years)
    daily["window"] = preprocessing.assign_window(daily["hydro_year"], wins)

    keys = ["gauge_id", "hydro_year"]
    annual = (
        annual_volume_metrics(daily)
        .merge(annual_timing_metrics(daily), on=keys, how="left")
        .merge(annual_variability_metrics(daily), on=keys, how="left")
        .merge(drivers.annual_driver_metrics(daily), on=keys, how="left")
    )
    if "runoff_mm" in annual and "precip_total_mm" in annual:
        annual["runoff_ratio"] = annual["runoff_mm"] / annual["precip_total_mm"]
    annual["window"] = preprocessing.assign_window(annual["hydro_year"], wins)

    flow_metrics = [m for m in FLOW_METRICS if m in annual]
    driver_metrics = [m for m in DRIVER_METRICS if m in annual]
    all_metrics = flow_metrics + driver_metrics

    min_years = min(15, s.filters.min_valid_years)  # fewer only for short records (e.g. tests)
    trend_tbl = trends.trend_table(annual, all_metrics, s.alpha, min_years=min_years)
    win_cmp = comparison.window_comparison(annual, all_metrics)
    corr = drivers.correlations(annual, flow_metrics, driver_metrics, min_years=min_years)
    attr_cols = [a for a in ATTRIBUTE_CANDIDATES if a in attrs]

    results = TrendResults(
        attributes=attrs,
        selection_log=selection_log,
        completeness=completeness,
        daily=daily,
        annual=annual,
        trends=trend_tbl,
        window_comparison=win_cmp,
        regime_monthly=seasonal.monthly_regime(daily),
        regime_daily=seasonal.daily_regime(daily),
        correlations=corr,
        correlation_summary=drivers.correlation_summary(corr, s.alpha),
        attribution=drivers.attribute_change(annual, min_years=min_years),
        trend_vs_attributes=comparison.trend_attribute_matrix(trend_tbl, attrs, all_metrics, attr_cols),
        meta=dict(
            units=units,
            selected_gauges=gauges,
            windows=[preprocessing.window_label(w) for w in wins],
            settings=asdict(s),
            **meta,
        ),
    )
    if save:
        results.save(s.processed_dir)
        log.info("Saved results to %s", s.processed_dir)
    return results


def _read_provenance(root: Path) -> dict:
    for parent in [root, *root.parents][:4]:
        p = parent / "provenance.json"
        if p.exists():
            return json.loads(p.read_text())
    return {}


def load(processed_dir: Path | None = None) -> TrendResults:
    directory = processed_dir or TrendSettings().processed_dir
    if not (directory / "meta.json").exists():
        raise FileNotFoundError(f"No cached results in {directory}. Run `python -m mountain_water.trend build`.")
    tables = {name: pd.read_parquet(directory / f"{name}.parquet") for name in TABLES}
    for name, df in tables.items():
        if "gauge_id" in df:
            df["gauge_id"] = df["gauge_id"].astype(str)
    return TrendResults(**tables, meta=json.loads((directory / "meta.json").read_text()))
