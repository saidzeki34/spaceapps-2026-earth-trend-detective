"""Station x month view: when flow is changing, and whether the same pattern appears across catchments.

One row per gauge, one column per calendar month plus three late-summer/annual summaries and the
half-volume date. Each cell is the Sen's slope of that annual value over a common period: volumes as %
of the station's baseline mean per decade, the half-volume date in days per decade (negative = earlier).

Unlike the main pipeline this uses calendar years (Jan-Dec) and its own selection:
    * CAMELS-CH gauges in one country (default "CH") on rivers (``water_body_type`` "stream"),
    * no missing or negative daily discharge on any day of the period (no gap filling),
    * ranked by mean catchment elevation, the highest ``n_gauges`` are kept.
There is no reservoir or hydropower filter. Reservoir and hydropower counts are kept in ``stations``
so regulated gauges can be flagged before their slopes are interpreted. Some catchments are nested.

Volumes use a 365-day year (29 February is left out), so leap years don't add a day to February,
the annual volume or the half-volume date.
"""

from __future__ import annotations

import calendar
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import camels_ch, trends
from .pipeline import _read_provenance
from .settings import StationNetworkSettings

log = logging.getLogger(__name__)

FLOW = "discharge_vol"
HM3_PER_M3S_DAY = 86400 / 1e6
LATE_SUMMER = (8, 9)
MONTHS = [f"m{m:02d}" for m in range(1, 13)]
SUMMARIES = ["aug_sep_hm3", "annual_hm3", "aug_sep_min7"]
TIMING = "half_volume_doy"
METRICS = MONTHS + SUMMARIES + [TIMING]
LABELS = {
    **{f"m{m:02d}": calendar.month_abbr[m] for m in range(1, 13)},
    "aug_sep_hm3": "Aug–Sep volume",
    "annual_hm3": "Annual volume",
    "aug_sep_min7": "Aug–Sep 7-day low",
    "half_volume_doy": "Half-volume date",
}
# Station context columns: alias -> CAMELS-CH attribute.
CONTEXT = {
    "river": "water_body_name",
    "name": "gauge_name",
    "elevation": "elev_mean",
    "area": "area",
    "glacier_area": "glac_area",
    "reservoirs": "num_reservoir",
    "hydropower_plants": "hp_count",
    "lat": "gauge_lat",
    "lon": "gauge_lon",
}
TABLES = ("stations", "selection_log", "annual", "trends")


@dataclass
class StationNetwork:
    stations: pd.DataFrame       # selected gauges in rank order (highest first) with label and context
    selection_log: pd.DataFrame  # gauges remaining after each selection step
    annual: pd.DataFrame         # one row per gauge and calendar year, one column per metric
    trends: pd.DataFrame         # one row per gauge and metric
    meta: dict = field(default_factory=dict)

    @property
    def gauges(self) -> list[str]:
        return self.stations["gauge_id"].tolist()

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in TABLES:
            getattr(self, name).to_parquet(directory / f"{name}.parquet", index=False)
        (directory / "meta.json").write_text(json.dumps(self.meta, indent=2, default=str))


def _label(row: pd.Series) -> str:
    river = str(row.get("river", "")).replace("_", " ")
    name = str(row.get("name", "")).replace("_", " ")
    elev = row.get("elevation")
    elev = f" · {elev:,.0f} m" if pd.notna(elev) else ""
    return f"{river} – {name} ({row['gauge_id']}){elev}"


def candidates(attrs: pd.DataFrame, s: StationNetworkSettings) -> tuple[list[str], list[tuple[str, int]]]:
    """Gauges passing the attribute filters, highest mean catchment elevation first, plus the step log."""
    keep = attrs.copy()
    steps = [("CAMELS-CH catchments", len(keep))]
    for column, wanted in (("country", s.country), ("water_body_type", s.water_body_type)):
        if wanted is None:
            continue
        if column not in keep:
            log.warning("Filter '%s == %s' skipped: no column", column, wanted)
            steps.append((f"{column} == {wanted}: SKIPPED (no column)", len(keep)))
            continue
        keep = keep[keep[column].astype(str) == wanted]
        steps.append((f"{column} == {wanted}", len(keep)))
    keep = keep.assign(_elev=pd.to_numeric(keep.get(CONTEXT["elevation"]), errors="coerce")).dropna(subset=["_elev"])
    steps.append(("mean catchment elevation known [elev_mean]", len(keep)))
    return keep.sort_values("_elev", ascending=False, kind="stable")["gauge_id"].tolist(), steps


def complete_gauges(obs: pd.DataFrame, first_year: int, last_year: int) -> set[str]:
    """Gauges with a valid (non-missing, non-negative) discharge on every day from first_year to last_year
    and some flow in every year (a year without flow has no half-volume date)."""
    period = obs[obs["date"].dt.year.between(first_year, last_year)]
    ok = period[period[FLOW].notna() & (period[FLOW] >= 0)]
    expected = len(pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31"))
    n_days = ok.groupby("gauge_id")["date"].nunique()
    driest_year = ok.groupby(["gauge_id", ok["date"].dt.year])[FLOW].sum().groupby("gauge_id").min()
    return set(n_days.index[(n_days == expected) & (driest_year.reindex(n_days.index) > 0)])


def _half_volume_day(q: pd.Series) -> float:
    """Day of the 365-day year (1 = 1 January) on which half of the year's volume has passed."""
    values = q.to_numpy(dtype=float)
    total = values.sum()
    if not total > 0:
        return np.nan
    return float(np.searchsorted(np.cumsum(values), total / 2) + 1)


def annual_metrics(daily: pd.DataFrame) -> pd.DataFrame:
    """Monthly and Aug-Sep volumes (hm³), annual volume, Aug-Sep 7-day low (m³/s), half-volume date."""
    d = daily[~((daily["date"].dt.month == 2) & (daily["date"].dt.day == 29))].sort_values(["gauge_id", "date"])
    d = d.assign(year=d["date"].dt.year, month=d["date"].dt.month, vol=d[FLOW] * HM3_PER_M3S_DAY)
    keys = ["gauge_id", "year"]
    out = d.groupby(keys + ["month"])["vol"].sum(min_count=1).unstack("month")
    out.columns = [f"m{m:02d}" for m in out.columns]
    late = d[d["month"].isin(LATE_SUMMER)].groupby(keys)
    out["aug_sep_hm3"] = late["vol"].sum(min_count=1)
    out["annual_hm3"] = d.groupby(keys)["vol"].sum(min_count=1)
    # 7-day windows that lie entirely within August-September.
    out["aug_sep_min7"] = late[FLOW].apply(lambda q: q.rolling(7, min_periods=7).mean().min())
    out[TIMING] = d.groupby(keys)[FLOW].apply(_half_volume_day)
    return out.reindex(columns=METRICS).reset_index()


def trend_table(annual: pd.DataFrame, baseline: tuple[int, int], alpha: float = 0.05) -> pd.DataFrame:
    """Sen's slope per decade relative to the baseline mean, Mann-Kendall p (pre-whitened) and FDR per metric."""
    rows = []
    for gauge_id, grp in annual.groupby("gauge_id", sort=False):
        grp = grp.sort_values("year")
        years = grp["year"].to_numpy(dtype=float)
        in_base = grp["year"].between(*baseline).to_numpy()
        for metric in METRICS:
            values = grp[metric].to_numpy(dtype=float)
            slope, _ = trends.sen_slope(years, values)
            base = values[in_base & np.isfinite(values)]
            base_mean = float(base.mean()) if len(base) else np.nan
            if metric == TIMING:
                change, unit = slope * 10, "days per decade"
            else:
                change = slope * 10 / base_mean * 100 if base_mean > 0 else np.nan
                unit = "% of baseline mean per decade"
            rows.append(dict(
                gauge_id=gauge_id, metric=metric, label=LABELS[metric], n_years=int(np.isfinite(values).sum()),
                baseline_mean=base_mean, slope_per_decade=slope * 10, change_per_decade=change, unit=unit,
                p=trends.mann_kendall_p(values),
            ))
    out = pd.DataFrame(rows)
    out["p_fdr"] = out.groupby("metric", group_keys=False)["p"].apply(trends.benjamini_hochberg)
    out["significant_fdr"] = out["p_fdr"] < alpha
    return out


def build(settings: StationNetworkSettings | None = None, save: bool = True) -> StationNetwork:
    s = settings or StationNetworkSettings()
    root = camels_ch.find_dataset_root(s.raw_dir)
    attrs = camels_ch.load_attributes(root)
    ranked, steps = candidates(attrs, s)
    obs, units = camels_ch.load_observed(root, ranked)
    if units.get(FLOW) not in (None, "m3/s"):
        raise ValueError(f"Expected {FLOW} in m3/s, the dataset says {units.get(FLOW)}")

    complete = complete_gauges(obs, s.first_year, s.last_year)
    ranked = [g for g in ranked if g in complete]
    complete_step = (f"complete daily discharge {s.first_year}–{s.last_year} "
                     "(no missing or negative days, flow in every year)")
    steps.append((complete_step, len(ranked)))
    gauges = ranked[: s.n_gauges]
    steps.append((f"highest {s.n_gauges} by mean catchment elevation", len(gauges)))
    if not gauges:
        raise ValueError("No gauges left after selection:\n" + "\n".join(f"{a}: {b}" for a, b in steps))

    stations = pd.DataFrame({"rank": range(1, len(gauges) + 1), "gauge_id": gauges})
    context = attrs.set_index("gauge_id").reindex(gauges)
    for alias, column in CONTEXT.items():
        stations[alias] = context[column].to_numpy() if column in context else np.nan
    stations["glacier_pct"] = 100 * pd.to_numeric(stations["glacier_area"], errors="coerce") / \
        pd.to_numeric(stations["area"], errors="coerce")
    stations["label"] = stations.apply(_label, axis=1)

    daily = obs[obs["gauge_id"].isin(gauges) & obs["date"].dt.year.between(s.first_year, s.last_year)]
    annual = annual_metrics(daily)
    network = StationNetwork(
        stations=stations,
        selection_log=pd.DataFrame(steps, columns=["step", "remaining"]),
        annual=annual,
        trends=trend_table(annual, s.baseline, s.alpha),
        meta=dict(source="camels_ch", dataset_root=str(root), provenance=_read_provenance(root),
                  units=dict(volume="hm³", aug_sep_min7="m³/s", half_volume_doy="day of 365-day year"),
                  settings=asdict(s)),
    )
    if save:
        network.save(s.processed_dir)
        log.info("Saved station network to %s", s.processed_dir)
    return network


def load(processed_dir: Path | None = None) -> StationNetwork:
    directory = processed_dir or StationNetworkSettings().processed_dir
    if not (directory / "meta.json").exists():
        raise FileNotFoundError(f"No station network in {directory}. Run `python -m mountain_water.trend stations`.")
    tables = {name: pd.read_parquet(directory / f"{name}.parquet") for name in TABLES}
    for df in tables.values():
        if "gauge_id" in df:
            df["gauge_id"] = df["gauge_id"].astype(str)
    return StationNetwork(**tables, meta=json.loads((directory / "meta.json").read_text()))


# --------------------------------------------------------------------------- derived tables


def change_matrix(network: StationNetwork, column: str = "change_per_decade") -> pd.DataFrame:
    """Gauges (rank order) x metrics."""
    m = network.trends.pivot(index="gauge_id", columns="metric", values=column)
    return m.reindex(index=network.gauges, columns=METRICS)


def summary(network: StationNetwork) -> pd.DataFrame:
    """Per metric across gauges: how many slopes are negative / positive, the median, how many are significant."""
    t = network.trends
    g = t.groupby("metric", sort=False)
    out = pd.DataFrame({
        "label": g["label"].first(),
        "unit": g["unit"].first(),
        "n_gauges": g["change_per_decade"].count(),
        "n_negative": g["slope_per_decade"].apply(lambda v: int((v < 0).sum())),
        "n_positive": g["slope_per_decade"].apply(lambda v: int((v > 0).sum())),
        "median_change_per_decade": g["change_per_decade"].median(),
        "n_significant_fdr_negative": t[t["significant_fdr"] & (t["slope_per_decade"] < 0)].groupby("metric").size(),
        "n_significant_fdr_positive": t[t["significant_fdr"] & (t["slope_per_decade"] > 0)].groupby("metric").size(),
    }).reindex(METRICS)
    sig = ["n_significant_fdr_negative", "n_significant_fdr_positive"]
    out[sig] = out[sig].fillna(0).astype(int)
    return out.rename_axis("metric").reset_index()


def wide_table(network: StationNetwork) -> pd.DataFrame:
    """One row per gauge with context and one column per metric (export twin of the heatmap)."""
    m = change_matrix(network)
    m.columns = [f"{LABELS[c]} ({'days' if c == TIMING else '% of baseline'} per decade)" for c in m.columns]
    cols = ["rank", "gauge_id", "river", "name", "elevation", "area", "glacier_pct", "reservoirs", "hydropower_plants"]
    return network.stations[cols].merge(m, left_on="gauge_id", right_index=True)


def year_anomalies(network: StationNetwork) -> pd.DataFrame:
    """Per gauge and year: Aug-Sep volume in % relative to the baseline mean, half-volume date minus baseline mean."""
    b0, b1 = network.meta["settings"]["baseline"]
    a = network.annual
    base = a[a["year"].between(b0, b1)].groupby("gauge_id")[["aug_sep_hm3", TIMING]].mean()
    out = a[["gauge_id", "year"]].copy()
    out["aug_sep_pct"] = 100 * (a["aug_sep_hm3"] / a["gauge_id"].map(base["aug_sep_hm3"]) - 1)
    out["half_volume_days"] = a[TIMING] - a["gauge_id"].map(base[TIMING])
    return out
