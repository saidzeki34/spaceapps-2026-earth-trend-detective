"""Station x month view: when flow is changing, and whether the same pattern appears across catchments.

One row per gauge, one column per calendar month plus three late-summer/annual summaries and the
half-volume date. Each cell is the Sen's slope of that annual value over a common period: volumes as %
of the station's baseline mean per decade (also in mm of runoff per decade), the half-volume date in
days per decade (negative = earlier).

Unlike the main pipeline this uses calendar years (Jan-Dec) and its own selections:
    * Switzerland: CAMELS-CH gauges in one country (default "CH") on rivers (``water_body_type``
      "stream") with no missing or negative daily discharge on any day of the period and flow in every
      year, ranked by mean catchment elevation; the highest ``n_gauges`` are kept.
    * Norway: the NVE mountain selection of the last ``build --source nve`` (median elevation,
      unregulated), ranked by median catchment elevation.
A year counts only if every day has a valid discharge (no gap filling). Slopes are only estimated for
gauges with enough complete years (``min_complete_years``, ``min_baseline_years`` in the baseline);
the others stay in the tables with empty slopes. There is no reservoir or hydropower filter in
Switzerland; ``infrastructure`` flags gauges with a recorded reservoir, hydropower plant or regulation.
Some catchments are nested.

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

from . import camels_ch, nve, pipeline, trends
from .drivers import _swe_dates
from .settings import StationNetworkSettings

log = logging.getLogger(__name__)

FLOW = "discharge_vol"
HM3_PER_M3S_DAY = 86400 / 1e6
LATE_SUMMER = (8, 9)
MONTHS = [f"m{m:02d}" for m in range(1, 13)]
SUMMARIES = ["aug_sep_hm3", "annual_hm3", "aug_sep_min7"]
TIMING = "half_volume_doy"
METRICS = MONTHS + SUMMARIES + [TIMING]
DRIVERS = ["snow_free_doy", "precip_jul_sep_mm"]
LABELS = {
    **{f"m{m:02d}": calendar.month_abbr[m] for m in range(1, 13)},
    "aug_sep_hm3": "Aug–Sep volume",
    "annual_hm3": "Annual volume",
    "aug_sep_min7": "Aug–Sep 7-day low",
    "half_volume_doy": "Half-volume date",
    "snow_free_doy": "Snow-free date",
    "precip_jul_sep_mm": "Jul–Sep precipitation",
}
# Flow metric vs driver, compared as changes per decade over the years both are available.
DRIVER_PAIRS = [("half_volume_doy", "snow_free_doy"), ("aug_sep_min7", "precip_jul_sep_mm")]
DATES = {TIMING, "snow_free_doy"}
COUNTRIES = {"ch": "Switzerland", "no": "Norway"}
# Swiss station context columns: alias -> CAMELS-CH attribute.
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
STATION_COLUMNS = ["country", "rank", "gauge_id", "river", "name", "elevation", "elevation_statistic", "area",
                   "glacier_pct", "reservoirs", "hydropower_plants", "infrastructure", "lat", "lon"]
TABLES = ("stations", "selection_log", "annual", "trends")


@dataclass
class StationNetwork:
    stations: pd.DataFrame       # gauges by country, highest catchment first, with context and record length
    selection_log: pd.DataFrame  # gauges remaining after each selection step, per country
    annual: pd.DataFrame         # one row per gauge and complete calendar year, one column per metric/driver
    trends: pd.DataFrame         # one row per gauge and metric (empty slopes where the record is too short)
    meta: dict = field(default_factory=dict)

    @property
    def gauges(self) -> list[str]:
        return self.stations["gauge_id"].tolist()

    @property
    def countries(self) -> list[str]:
        return list(dict.fromkeys(self.stations["country"]))

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in TABLES:
            getattr(self, name).to_parquet(directory / f"{name}.parquet", index=False)
        (directory / "meta.json").write_text(json.dumps(self.meta, indent=2, default=str))


def _label(row: pd.Series) -> str:
    river = str(row.get("river", "") or "").replace("_", " ")
    name = str(row.get("name", "") or "").replace("_", " ")
    elev = row.get("elevation")
    elev = f" · {elev:,.0f} m" if pd.notna(elev) else ""
    marks = (" ▲" if row.get("glacier_pct", 0) > 0 else "") + (" ■" if row.get("infrastructure") else "")
    return f"{river} – {name} ({row['gauge_id']}){elev}{marks}"


# --------------------------------------------------------------------------- selections


def candidates(attrs: pd.DataFrame, s: StationNetworkSettings) -> tuple[list[str], list[tuple[str, int]]]:
    """Swiss gauges passing the attribute filters, highest mean catchment elevation first, plus the step log."""
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
    status = year_status(obs[obs["date"].dt.year.between(first_year, last_year)])
    n_years = status[status["complete"]].groupby("gauge_id").size()
    return set(n_years.index[n_years == last_year - first_year + 1])


def year_status(daily: pd.DataFrame) -> pd.DataFrame:
    """Per gauge and calendar year: complete = every day has a valid discharge and the year has some flow."""
    ok = daily[daily[FLOW].notna() & (daily[FLOW] >= 0)]
    g = ok.groupby(["gauge_id", ok["date"].dt.year.rename("year")])
    out = pd.DataFrame({"n_valid": g["date"].nunique(), "total": g[FLOW].sum()}).reset_index()
    days = np.where([calendar.isleap(int(y)) for y in out["year"]], 366, 365)
    out["complete"] = (out["n_valid"] == days) & (out["total"] > 0)
    return out[["gauge_id", "year", "complete"]]


def _swiss(s: StationNetworkSettings) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[str, int]], dict]:
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

    stations = pd.DataFrame({"gauge_id": gauges})
    context = attrs.set_index("gauge_id").reindex(gauges)
    for alias, column in CONTEXT.items():
        stations[alias] = context[column].to_numpy() if column in context else np.nan
    stations["glacier_pct"] = 100 * pd.to_numeric(stations["glacier_area"], errors="coerce") / \
        pd.to_numeric(stations["area"], errors="coerce")
    stations["infrastructure"] = (pd.to_numeric(stations["reservoirs"], errors="coerce").fillna(0) > 0) | \
        (pd.to_numeric(stations["hydropower_plants"], errors="coerce").fillna(0) > 0)
    stations["elevation_statistic"] = "mean"
    meta = dict(dataset="CAMELS-CH observed daily discharge", dataset_root=str(root),
                provenance=pipeline._read_provenance(root))
    return stations, obs[obs["gauge_id"].isin(gauges)], steps, meta


def _norway(s: StationNetworkSettings) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[str, int]], dict]:
    if not (s.nve_selection_dir / "meta.json").exists():
        raise FileNotFoundError(f"No NVE selection in {s.nve_selection_dir}. Run `build --source nve` first.")
    selection = [str(g) for g in json.loads((s.nve_selection_dir / "meta.json").read_text())["selected_gauges"]]
    attrs = nve.load_stations(s.nve_raw_dir)
    obs, _ = nve.load_daily(s.nve_raw_dir, attrs)
    obs = obs[obs["gauge_id"].isin(selection)]
    gauges = [g for g in selection if g in set(obs["gauge_id"])]
    steps = [("NVE mountain selection (last `build --source nve`)", len(selection)),
             ("daily discharge cached", len(gauges))]

    a = attrs.set_index("gauge_id").reindex(gauges)
    stations = pd.DataFrame({
        "gauge_id": gauges,
        "river": a["riverName"].to_numpy() if "riverName" in a else "",
        "name": a["name"].to_numpy(),
        "elevation": pd.to_numeric(a["elevation"], errors="coerce").to_numpy(),
        "area": pd.to_numeric(a["area"], errors="coerce").to_numpy(),
        "glacier_pct": pd.to_numeric(a["glacier"], errors="coerce").to_numpy(),
        "reservoirs": np.nan, "hydropower_plants": np.nan,
        "infrastructure": pd.to_numeric(a["regulated"], errors="coerce").fillna(0).to_numpy() > 0,
        "lat": a["lat"].to_numpy() if "lat" in a else np.nan, "lon": a["lon"].to_numpy() if "lon" in a else np.nan,
    })
    stations = stations.sort_values("elevation", ascending=False, kind="stable").reset_index(drop=True)
    stations["elevation_statistic"] = "median"
    meta = dict(dataset="NVE HydAPI daily discharge (1001) + seNorge via GTS", raw_dir=str(s.nve_raw_dir))
    return stations, obs, steps, meta


# --------------------------------------------------------------------------- annual values and trends


def _half_volume_day(q: pd.Series) -> float:
    """Day of the 365-day year (1 = 1 January) on which half of the year's volume has passed."""
    values = q.to_numpy(dtype=float)
    total = values.sum()
    if not total > 0:
        return np.nan
    return float(np.searchsorted(np.cumsum(values), total / 2) + 1)


def _snow_free_day(swe: pd.Series, min_peak: float) -> float:
    """First day after the Jan-Aug SWE peak with SWE <= 5 % of the peak (day of the 365-day year).

    Only January-August is searched: CAMELS-CH and seNorge SWE drop to ~0 at the start of September
    (checked in the data: e.g. gauge 2009 goes from 43 mm to 0 between 1 and 2 September 2010), which is
    a reset, not melt. Years still above 5 % of the peak on 31 August get no date.
    """
    values = swe.to_numpy(dtype=float)[:243]  # 1 January - 31 August
    if len(values) < 243 or np.isnan(values).any() or values.max() < min_peak:
        return np.nan
    return _swe_dates(np.arange(1, len(values) + 1, dtype=float), values)[1]


def annual_metrics(daily: pd.DataFrame, min_peak_swe_mm: float = 10.0) -> pd.DataFrame:
    """Per gauge and complete calendar year: monthly and Aug-Sep volumes (hm³), annual volume, Aug-Sep
    7-day low (m³/s), half-volume date and, where the series exist, snow-free date and Jul-Sep precipitation."""
    status = year_status(daily)
    complete = status.loc[status["complete"], ["gauge_id", "year"]]
    d = daily.assign(year=daily["date"].dt.year).merge(complete, on=["gauge_id", "year"])
    d = d[~((d["date"].dt.month == 2) & (d["date"].dt.day == 29))].sort_values(["gauge_id", "date"])
    d = d.assign(month=d["date"].dt.month, vol=d[FLOW] * HM3_PER_M3S_DAY)
    keys = ["gauge_id", "year"]
    out = d.groupby(keys + ["month"])["vol"].sum(min_count=1).unstack("month")
    out.columns = [f"m{m:02d}" for m in out.columns]
    late = d[d["month"].isin(LATE_SUMMER)].groupby(keys)
    out["aug_sep_hm3"] = late["vol"].sum(min_count=1)
    out["annual_hm3"] = d.groupby(keys)["vol"].sum(min_count=1)
    # 7-day windows that lie entirely within August-September.
    out["aug_sep_min7"] = late[FLOW].apply(lambda q: q.rolling(7, min_periods=7).mean().min())
    out[TIMING] = d.groupby(keys)[FLOW].apply(_half_volume_day)
    if "swe" in d:
        out["snow_free_doy"] = d.groupby(keys)["swe"].apply(_snow_free_day, min_peak=min_peak_swe_mm)
    if "precipitation" in d:
        out["precip_jul_sep_mm"] = d[d["month"].isin((7, 8, 9))].groupby(keys)["precipitation"].sum(min_count=92)
    return out.reindex(columns=METRICS + DRIVERS).reset_index()


def record_length(annual: pd.DataFrame, baseline: tuple[int, int]) -> pd.DataFrame:
    """Complete years per gauge: total, in the baseline, first and last."""
    g = annual.groupby("gauge_id")["year"]
    return pd.DataFrame({
        "complete_years": g.size(),
        "baseline_years": annual[annual["year"].between(*baseline)].groupby("gauge_id").size(),
        "first_complete_year": g.min(),
        "last_complete_year": g.max(),
    })


def _runoff_change(metric: str, slope_per_decade: float, area_km2: float) -> tuple[float, str]:
    """Slope in mm of runoff over the catchment: hm³ -> mm per decade, the 7-day low m³/s -> mm/d per decade."""
    if metric == TIMING or not area_km2 > 0:
        return np.nan, ""
    if metric == "aug_sep_min7":
        return slope_per_decade * 86.4 / area_km2, "mm/d per decade"
    return slope_per_decade * 1000 / area_km2, "mm per decade"


def trend_table(annual: pd.DataFrame, stations: pd.DataFrame, baseline: tuple[int, int],
                alpha: float = 0.05) -> pd.DataFrame:
    """Sen's slope per decade relative to the baseline mean (and in mm), Mann-Kendall p (pre-whitened),
    FDR per metric over all gauges with sufficient data. Gauges without enough data get empty slopes."""
    rows = []
    info = stations.set_index("gauge_id")
    for gauge_id, grp in annual.groupby("gauge_id", sort=False):
        grp = grp.sort_values("year")
        years = grp["year"].to_numpy(dtype=float)
        in_base = grp["year"].between(*baseline).to_numpy()
        sufficient = bool(info.at[gauge_id, "sufficient"])
        for metric in METRICS:
            values = grp[metric].to_numpy(dtype=float)
            slope = trends.sen_slope(years, values)[0] if sufficient else np.nan
            base = values[in_base & np.isfinite(values)]
            base_mean = float(base.mean()) if len(base) else np.nan
            if metric == TIMING:
                change, unit = slope * 10, "days per decade"
            else:
                change = slope * 10 / base_mean * 100 if base_mean > 0 else np.nan
                unit = "% of baseline mean per decade"
            runoff, runoff_unit = _runoff_change(metric, slope * 10, info.at[gauge_id, "area"])
            rows.append(dict(
                gauge_id=gauge_id, country=info.at[gauge_id, "country"], metric=metric, label=LABELS[metric],
                n_years=int(np.isfinite(values).sum()), sufficient=sufficient, baseline_mean=base_mean,
                slope_per_decade=slope * 10, change_per_decade=change, unit=unit,
                runoff_change_per_decade=runoff, runoff_unit=runoff_unit,
                p=trends.mann_kendall_p(values) if sufficient else np.nan,
            ))
    out = pd.DataFrame(rows)
    out["p_fdr"] = out.groupby("metric", group_keys=False)["p"].apply(trends.benjamini_hochberg)
    out["significant_fdr"] = out["p_fdr"] < alpha
    return out


def build(settings: StationNetworkSettings | None = None, save: bool = True) -> StationNetwork:
    s = settings or StationNetworkSettings()
    loaders = {"ch": _swiss, "no": _norway}
    stations, daily, steps, sources = [], [], [], {}
    for region in s.regions:
        st, obs, region_steps, meta = loaders[region](s)
        country = COUNTRIES[region]
        stations.append(st.assign(country=country))
        daily.append(obs[obs.columns.intersection(["gauge_id", "date", FLOW, "swe", "precipitation"])])
        steps += [(country, step, n) for step, n in region_steps]
        sources[country] = meta
    stations = pd.concat(stations, ignore_index=True)
    daily = pd.concat(daily, ignore_index=True)
    daily = daily[daily["date"].dt.year.between(s.first_year, s.last_year)]
    if stations.empty:
        raise ValueError("No gauges left after selection:\n" + "\n".join(f"{c}: {a}: {b}" for c, a, b in steps))

    annual = annual_metrics(daily, s.min_peak_swe_mm)
    stations = stations.join(record_length(annual, s.baseline), on="gauge_id")
    counts = ["complete_years", "baseline_years"]
    stations[counts] = stations[counts].fillna(0).astype(int)
    stations["sufficient"] = (stations["complete_years"] >= s.min_complete_years) & \
        (stations["baseline_years"] >= s.min_baseline_years)
    stations["rank"] = stations.groupby("country").cumcount() + 1
    stations = stations[STATION_COLUMNS + [c for c in stations if c not in STATION_COLUMNS]]
    stations["label"] = stations.apply(_label, axis=1)
    for country, g in stations.groupby("country", sort=False):
        steps.append((country, f">= {s.min_complete_years} complete years, >= {s.min_baseline_years} in "
                               f"{s.baseline[0]}–{s.baseline[1]} (slopes estimated)", int(g["sufficient"].sum())))

    network = StationNetwork(
        stations=stations,
        selection_log=pd.DataFrame(steps, columns=["country", "step", "remaining"]),
        annual=annual,
        trends=trend_table(annual, stations, s.baseline, s.alpha),
        meta=dict(sources=sources, settings=asdict(s),
                  units=dict(volume="hm³", aug_sep_min7="m³/s", half_volume_doy="day of 365-day year",
                             snow_free_doy="day of 365-day year", precip_jul_sep_mm="mm")),
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
    """Gauges (table order) x metrics."""
    m = network.trends.pivot(index="gauge_id", columns="metric", values=column)
    return m.reindex(index=network.gauges, columns=METRICS)


def summary(network: StationNetwork, by_infrastructure: bool = False) -> pd.DataFrame:
    """Per country and metric over gauges with sufficient data: negative / positive slopes, medians,
    significant slopes. ``by_infrastructure`` splits gauges with and without a recorded reservoir,
    hydropower plant or regulation."""
    t = network.trends[network.trends["sufficient"]]
    t = t.assign(infrastructure=t["gauge_id"].map(network.stations.set_index("gauge_id")["infrastructure"]))
    keys = ["country", "infrastructure", "metric"] if by_infrastructure else ["country", "metric"]
    g = t.groupby(keys, sort=False)
    sig = t[t["significant_fdr"]]
    out = pd.DataFrame({
        "label": g["label"].first(),
        "unit": g["unit"].first(),
        "n_gauges": g["change_per_decade"].count(),
        "n_negative": g["slope_per_decade"].apply(lambda v: int((v < 0).sum())),
        "n_positive": g["slope_per_decade"].apply(lambda v: int((v > 0).sum())),
        "median_change_per_decade": g["change_per_decade"].median(),
        "median_runoff_change_per_decade": g["runoff_change_per_decade"].median(),
        "runoff_unit": g["runoff_unit"].first(),
        "n_significant_fdr_negative": sig[sig["slope_per_decade"] < 0].groupby(keys).size(),
        "n_significant_fdr_positive": sig[sig["slope_per_decade"] > 0].groupby(keys).size(),
    })
    cols = ["n_significant_fdr_negative", "n_significant_fdr_positive"]
    out[cols] = out[cols].fillna(0).astype(int)
    return out.reset_index()


def wide_table(network: StationNetwork) -> pd.DataFrame:
    """One row per gauge with context, record length and one column per metric (export twin of the heatmap)."""
    pct = change_matrix(network)
    pct.columns = [f"{LABELS[c]} ({'days' if c == TIMING else '% of baseline'} per decade)" for c in pct.columns]
    mm = change_matrix(network, "runoff_change_per_decade").drop(columns=TIMING)
    mm.columns = [f"{LABELS[c]} ({'mm/d' if c == 'aug_sep_min7' else 'mm'} per decade)" for c in mm.columns]
    cols = ["country", "rank", "gauge_id", "river", "name", "elevation", "elevation_statistic", "area", "glacier_pct",
            "reservoirs", "hydropower_plants", "infrastructure", "complete_years", "baseline_years",
            "first_complete_year", "last_complete_year", "sufficient"]
    return network.stations[cols].merge(pct, left_on="gauge_id", right_index=True) \
        .merge(mm, left_on="gauge_id", right_index=True)


def year_anomalies(network: StationNetwork) -> pd.DataFrame:
    """Per gauge and complete year: Aug-Sep volume in % relative to the baseline mean, half-volume date minus
    the baseline mean (days). Years without a complete record are absent."""
    b0, b1 = network.meta["settings"]["baseline"]
    a = network.annual
    base = a[a["year"].between(b0, b1)].groupby("gauge_id")[["aug_sep_hm3", TIMING]].mean()
    out = a[["gauge_id", "year"]].copy()
    out["aug_sep_pct"] = 100 * (a["aug_sep_hm3"] / a["gauge_id"].map(base["aug_sep_hm3"]) - 1)
    out["half_volume_days"] = a[TIMING] - a["gauge_id"].map(base[TIMING])
    return out


def _change(years: np.ndarray, values: np.ndarray, is_date: bool) -> float:
    """Sen's slope per decade: days for dates, otherwise % of the mean over the same years."""
    slope = trends.sen_slope(years, values)[0] * 10
    if is_date:
        return slope
    mean = values.mean()
    return slope / mean * 100 if mean > 0 else np.nan


def driver_changes(network: StationNetwork) -> pd.DataFrame:
    """Per gauge with sufficient data and flow-driver pair: change per decade of both, fitted over the same
    years (those where both values exist). Pairs with fewer than ``min_paired_years`` years are left out."""
    min_years = network.meta["settings"]["min_paired_years"]
    info = network.stations.set_index("gauge_id")
    annual = network.annual[network.annual["gauge_id"].map(info["sufficient"]).astype(bool)]
    rows = []
    for flow, driver in DRIVER_PAIRS:
        if driver not in annual:
            continue
        for gauge_id, grp in annual.groupby("gauge_id", sort=False):
            both = grp.dropna(subset=[flow, driver])
            if len(both) < min_years:
                continue
            years = both["year"].to_numpy(dtype=float)
            rows.append(dict(
                gauge_id=gauge_id, country=info.at[gauge_id, "country"], label=info.at[gauge_id, "label"],
                glacier_pct=info.at[gauge_id, "glacier_pct"], flow=flow, driver=driver, n_years=len(both),
                first_year=int(years.min()), last_year=int(years.max()),
                flow_change=_change(years, both[flow].to_numpy(dtype=float), flow in DATES),
                driver_change=_change(years, both[driver].to_numpy(dtype=float), driver in DATES),
            ))
    return pd.DataFrame(rows, columns=["gauge_id", "country", "label", "glacier_pct", "flow", "driver", "n_years",
                                       "first_year", "last_year", "flow_change", "driver_change"])
