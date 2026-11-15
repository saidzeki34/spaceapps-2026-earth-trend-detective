"""The shared graph and the statistics table for a measured (or imaginary) year."""

from __future__ import annotations

import calendar

import pandas as pd

from mountain_water.ui import controls, wording
from mountain_water.ui.controls import METHOD_MONTHLY, Variable
from mountain_water.ui.data_source import ALPHA, HYDRO_YEAR_START_MONTH, RiverData

# A monthly value is shown only when at least this share of the month's days has data.
MONTH_COVERAGE = 0.9
SECONDS_PER_DAY = 86400
_NON_LEAP_YEAR = 2001

_usual_cache: dict = {}


def _to_volume(mean_flow: float, days: int) -> float:
    """Mean discharge (m³/s) over a number of days -> volume in million m³."""
    return mean_flow * days * SECONDS_PER_DAY / 1e6


def monthly_values(data: RiverData, variable: Variable, year: int) -> list[float | None]:
    """One value per calendar month; None where the month is not covered well enough."""
    if variable.column not in data.daily:
        return [None] * 12
    rows = data.daily[data.daily["date"].dt.year == year]
    by_month = rows.groupby(rows["date"].dt.month)[variable.column]
    counts, means = by_month.count(), by_month.mean()
    values: list[float | None] = []
    for month in range(1, 13):
        days = calendar.monthrange(year, month)[1]
        if counts.get(month, 0) >= MONTH_COVERAGE * days:
            mean = float(means[month])
            values.append(_to_volume(mean, days) if variable.as_volume else mean)
        else:
            values.append(None)
    return values


def daily_values(data: RiverData, variable: Variable, year: int) -> list[float | None]:
    """One value per day of the calendar year; None where there is no measurement."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    if variable.column not in data.daily:
        return [None] * len(days)
    rows = data.daily[data.daily["date"].dt.year == year]
    series = rows.set_index("date")[variable.column].reindex(days)
    if variable.as_volume:
        series = series * SECONDS_PER_DAY / 1e6
    return [None if pd.isna(v) else float(v) for v in series]


def usual_monthly(data: RiverData, variable: Variable) -> list[float | None]:
    """The usual value of each calendar month over the whole record (trend section's monthly regime)."""
    key = (data.river.id, variable.id, "months")
    if key not in _usual_cache:
        values: list[float | None] = [None] * 12
        if variable.column in data.daily:
            from mountain_water.trend import seasonal

            regime = seasonal.monthly_regime(data.daily.assign(window="all"), column=variable.column)
            by_month = regime.set_index("month")["mean"]
            for month in range(1, 13):
                mean = by_month.get(month)
                if mean is not None and pd.notna(mean):
                    days = calendar.monthrange(_NON_LEAP_YEAR, month)[1]
                    values[month - 1] = _to_volume(float(mean), days) if variable.as_volume else float(mean)
        _usual_cache[key] = values
    return _usual_cache[key]


def usual_daily(data: RiverData, variable: Variable, year: int) -> list[float | None]:
    """The usual value of each day of the year (trend section's day-of-year climatology)."""
    key = (data.river.id, variable.id, "days")
    if key not in _usual_cache:
        by_day: dict[tuple[int, int], float] = {}
        if variable.column in data.daily:
            from mountain_water.trend import baseline

            climatology = baseline.daily_climatology(data.daily, data.river.id, column=variable.column)
            first_day = pd.Timestamp(year=_NON_LEAP_YEAR - 1, month=HYDRO_YEAR_START_MONTH, day=1)
            for hydro_day, mean in zip(climatology["hydro_doy"], climatology["mean"]):
                if pd.notna(mean):
                    date = first_day + pd.Timedelta(days=int(hydro_day) - 1)
                    value = float(mean) * SECONDS_PER_DAY / 1e6 if variable.as_volume else float(mean)
                    by_day[(date.month, date.day)] = value
        _usual_cache[key] = by_day
    by_day = _usual_cache[key]
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    # 29 February has no day of its own in the climatology; it borrows the 28th.
    return [by_day.get((d.month, d.day), by_day.get((2, 28)) if (d.month, d.day) == (2, 29) else None) for d in days]


def chart(data: RiverData, variable_ids: list[str], year: int, method: str, with_usual: bool) -> dict:
    """All ticked variables as lines of one graph."""
    monthly = method == METHOD_MONTHLY
    series = []
    for variable_id in variable_ids:
        variable = controls.VARIABLES_BY_ID[variable_id]
        values = monthly_values(data, variable, year) if monthly else daily_values(data, variable, year)
        usual = None
        if with_usual:
            usual = usual_monthly(data, variable) if monthly else usual_daily(data, variable, year)
        series.append({
            "id": variable.id, "label": variable.label, "unit": variable.unit, "color": variable.color,
            "group": variable.group, "values": values, "usual": usual,
            "imaginary": data.is_imaginary(variable.column), "predicted": False,
        })
    count = 12 if monthly else (366 if calendar.isleap(year) else 365)
    return {"x": {"kind": "months" if monthly else "days", "year": year, "count": count}, "series": series}


def statistics(data: RiverData, variable_ids: list[str], year: int, predicted: bool) -> dict:
    """Yearly figures and long-term change of each ticked variable, from the trend section's tables."""
    from mountain_water.trend.registry import info

    this_year = data.annual[data.annual["hydro_year"] == year]
    rows = []
    period = ""
    for variable_id in variable_ids:
        variable = controls.VARIABLES_BY_ID[variable_id]
        meta = info(variable.trend_metric)
        unit = "" if meta.unit == "-" else meta.unit
        row = {
            "variable": variable.label, "color": variable.color, "metric": meta.label, "unit": unit,
            "year_value": "—", "mean": "—", "change": "not enough years", "evidence": "",
            "significant": False, "imaginary": data.is_imaginary(variable.column),
        }
        if not predicted and not this_year.empty and variable.trend_metric in this_year:
            row["year_value"] = wording.number(float(this_year[variable.trend_metric].iloc[0]))
        trend = data.trends[data.trends["metric"] == variable.trend_metric]
        if not trend.empty:
            t = trend.iloc[0]
            row["mean"] = wording.number(float(t["mean"]))
            row["change"] = wording.signed(float(t["slope_per_decade"]), unit) + " per decade"
            if wording.is_number(float(t["pct_per_decade"])):
                row["change"] += f" ({wording.signed(float(t['pct_per_decade']))} %)"
            p = float(t["p"])
            row["significant"] = wording.is_number(p) and p < ALPHA
            row["evidence"] = ("significant, " if row["significant"] else "not significant, ") + wording.p_value(p)
            period = f"{int(t['first_year'])}–{int(t['last_year'])}"
        rows.append(row)
    return {
        "rows": rows,
        "year_label": None if predicted or this_year.empty else f"Oct {year - 1} – Sep {year}",
        "period": period,
        "note": (
            "Yearly figures use the hydrological year (October to September), as in the trend analysis. "
            "Change per decade is a Sen's slope; the p-value comes from a Mann-Kendall test."
        ),
    }
