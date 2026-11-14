"""Interval integration and complete-period summaries."""
import numpy as np
import pandas as pd

from mountain_water.contracts import FlowSeries


def durations(table):
    return (table.end - table.start).dt.total_seconds()


def local_dates(flow: FlowSeries):
    return flow.table.start.dt.tz_convert(flow.outlet.calendar_timezone)


def interval_volume(table: pd.DataFrame) -> pd.Series:
    return (table.discharge_m3s * durations(table)).where(table.valid)


def calculate_flow_metrics(table: pd.DataFrame, start, end) -> dict:
    seconds = durations(table)
    valid = table.valid & table.discharge_m3s.notna()
    expected = (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds()
    assessed = float(seconds[valid].sum())
    observed_volume = float(interval_volume(table).sum(min_count=1)) if valid.any() else None
    complete = expected > 0 and np.isclose(assessed, expected, atol=0.01, rtol=0)
    q = table.loc[valid, "discharge_m3s"]
    return {"observed_volume_m3": observed_volume,
            "complete_volume_m3": observed_volume if complete else None,
            "coverage": assessed / expected if expected else 0,
            "assessed_seconds": assessed, "expected_seconds": expected,
            "low_flow_p10_m3s": float(q.quantile(.1)) if len(q) else None,
            "high_flow_p90_m3s": float(q.quantile(.9)) if len(q) else None,
            "quantile_basis": "valid interval means (equal daily durations required for interpretation)"}


def daily_table(flow: FlowSeries) -> pd.DataFrame:
    """Calendar summaries require aligned, full native 24-hour days."""
    t = flow.table.copy()
    dates = local_dates(flow)
    if not np.isclose(durations(t), 86400).all() or not (dates == dates.dt.normalize()).all():
        raise ValueError("Calendar analysis needs full 24-hour intervals at the outlet's calendar midnight.")
    t["date"] = dates.dt.tz_localize(None)
    t["year"] = t.date.dt.year
    t["month"] = t.date.dt.month
    return t


def period_summaries(flow: FlowSeries, months=tuple(range(1, 13)), water_year_start_month=10):
    t = daily_table(flow)
    columns = ["year", "start", "end", "coverage", "season_volume_m3", "annual_volume_m3",
               "half_volume_day", "annual_coverage", "valid_days", "expected_days"]
    if t.empty:
        return pd.DataFrame(columns=columns)
    # Water year is labelled by its starting calendar year, including January starts.
    t["water_year"] = t.year - (t.month < water_year_start_month).astype(int)
    rows = []
    for year in range(int(t.water_year.min()), int(t.water_year.max()) + 1):
        start = pd.Timestamp(year, water_year_start_month, 1)
        end = start + pd.DateOffset(years=1)
        days = pd.date_range(start, end, inclusive="left")
        selected_days = days[days.month.isin(months)]
        block = t[t.water_year == year].set_index("date").reindex(days)
        valid = block.valid.eq(True) & block.discharge_m3s.notna()
        season = block.loc[selected_days]
        good = valid.loc[selected_days]
        complete = bool(good.all()) and len(selected_days) > 0
        annual_complete = bool(valid.all())
        seasonal_volume = float(season.discharge_m3s.sum() * 86400) if complete else np.nan
        annual_volume = float(block.discharge_m3s.sum() * 86400) if annual_complete else np.nan
        midpoint = np.nan
        if annual_complete and annual_volume > 0:
            volumes = block.discharge_m3s.to_numpy() * 86400
            cumulative = np.cumsum(volumes)
            index = int(np.searchsorted(cumulative, annual_volume / 2, side="left"))
            previous = cumulative[index - 1] if index else 0
            # Elapsed days since start; within-day constant flow assumption is explicit.
            midpoint = index + (annual_volume / 2 - previous) / volumes[index]
        rows.append({"year": year, "start": start, "end": end,
                     "coverage": float(good.mean()), "season_volume_m3": seasonal_volume,
                     "annual_volume_m3": annual_volume, "half_volume_day": midpoint,
                     "annual_coverage": float(valid.mean()), "valid_days": int(good.sum()),
                     "expected_days": len(selected_days)})
    return pd.DataFrame(rows, columns=columns)


def monthly_means(flow: FlowSeries) -> pd.DataFrame:
    t = daily_table(flow)
    rows = []
    for (year, month), block in t.groupby(["year", "month"]):
        start = pd.Timestamp(year, month, 1, tz=flow.outlet.calendar_timezone).tz_convert("UTC")
        end = (pd.Timestamp(year, month, 1, tz=flow.outlet.calendar_timezone)
               + pd.DateOffset(months=1)).tz_convert("UTC")
        valid = block.valid & block.discharge_m3s.notna()
        expected = pd.Timestamp(year, month, 1).days_in_month
        complete = int(valid.sum()) == expected
        rows.append({"start": start, "end": end, "month": month, "year": year,
                     "value": float(block.discharge_m3s.mean()) if complete else np.nan,
                     "coverage": float(valid.sum() / expected)})
    return pd.DataFrame(rows, columns=["start", "end", "month", "year", "value", "coverage"])
