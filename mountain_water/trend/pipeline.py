"""End-to-end trend pipeline: parse -> filter -> annual metrics -> trends, window comparison, drivers.

Usage from Python (e.g. Streamlit)::

    from mountain_water.trend import pipeline
    results = pipeline.load()          # cached tables from data/processed/trend
    results = pipeline.build()         # recompute from data/raw/camels_ch
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from . import camels_ch, comparison, drivers, preprocessing, seasonal, trends
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
        (directory / "meta.json").write_text(json.dumps(self.meta, indent=2, default=str))


def _standard_columns(attrs: pd.DataFrame) -> pd.DataFrame:
    """Add stable alias columns (name, lat, lon, elevation, ...) next to the original attribute names."""
    out = attrs.copy()
    for alias, candidates in {**LABEL_CANDIDATES, **ATTRIBUTE_CANDIDATES}.items():
        col = next((c for c in candidates if c in out.columns), None)
        if col is not None and alias not in out.columns:
            out[alias] = out[col]
    return out


def build(settings: TrendSettings | None = None, save: bool = True) -> TrendResults:
    s = settings or TrendSettings()
    root = camels_ch.find_dataset_root(s.raw_dir)
    log.info("Reading CAMELS-CH from %s", root)

    attrs = _standard_columns(camels_ch.load_attributes(root))
    obs, units = camels_ch.load_observed(root)
    obs = preprocessing.add_hydro_year(obs, s.hydro_year_start_month)
    obs = preprocessing.fill_short_gaps(obs, GAP_FILL_COLUMNS, s.max_gap_fill_days)
    completeness = preprocessing.year_completeness(obs, FLOW)

    gauges, selection_log = preprocessing.select_catchments(attrs, completeness, s.filters, s.min_year_completeness)
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

    trend_tbl = trends.trend_table(annual, all_metrics, s.alpha)
    win_cmp = comparison.window_comparison(annual, all_metrics)
    corr = drivers.correlations(annual, flow_metrics, driver_metrics)
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
        attribution=drivers.attribute_change(annual),
        trend_vs_attributes=comparison.trend_attribute_matrix(trend_tbl, attrs, all_metrics, attr_cols),
        meta=dict(
            dataset_root=str(root),
            units=units,
            selected_gauges=gauges,
            windows=[preprocessing.window_label(w) for w in wins],
            settings=asdict(s),
            provenance=_read_provenance(root),
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
