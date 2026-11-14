"""Calendar-day historical distribution, explicitly separate from demand."""
import pandas as pd

from mountain_water.analysis.flow_metrics import daily_table
from mountain_water.contracts import FlowSeries


def build_baseline(flow: FlowSeries, baseline_years: tuple[int, int]) -> pd.DataFrame:
    t = daily_table(flow)
    t = t[t.year.between(*baseline_years)].copy()
    t["day"] = t.date.dt.strftime("%m-%d")
    t["value"] = t.discharge_m3s.where(t.valid)
    reference = pd.date_range(f"{baseline_years[0]}-01-01", f"{baseline_years[1]}-12-31")
    expected = pd.Series(reference.strftime("%m-%d")).value_counts().sort_index()
    grouped = t.groupby("day").value
    result = grouped.agg(mean="mean", median="median", count="count")
    result["p10"] = grouped.quantile(.1)
    result["p90"] = grouped.quantile(.9)
    result = result.reindex(expected.index)
    result["count"] = result["count"].fillna(0).astype(int)
    result["expected"] = expected
    result["completeness"] = result["count"] / result.expected
    result.index.name = "day"
    return result.reset_index()


def align_baseline(table: pd.DataFrame, baseline: pd.DataFrame, timezone: str):
    t = table.copy()
    t["day"] = t.start.dt.tz_convert(timezone).dt.strftime("%m-%d")
    return t.merge(baseline, on="day", how="left", validate="many_to_one")
