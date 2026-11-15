"""The risk assessment for the chosen occupation.

The requirement is an imaginary scenario for now (see ``controls.py``). The
comparison of flow with it follows the team's project guide: time below the
requirement, shortfall periods, their length and the missing volume. A day
without a measurement is never counted as short or as fine, and it ends a
shortfall period.

The comparison in this file is a stand-in. It belongs to
``mountain_water.risk_assessment``, which is still empty, and should move there.
"""

from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

from mountain_water.ui import data_source, imaginary, wording
from mountain_water.ui.controls import Occupation
from mountain_water.ui.data_source import ALPHA, HYDRO_YEAR_START_MONTH, RiverData

SECONDS_PER_DAY = 86400
# A year enters the long-term comparison when at least this share of its days has flow data.
YEAR_COVERAGE = 0.9
QUANTITY_METRIC = "volume_hm3"
TIMING_METRIC = "half_volume_doy"

_plane_cache: dict = {}


def flow_reference(data: RiverData) -> dict[str, float]:
    """Long-term mean, median and Q347 of the river's daily flow."""
    from mountain_water.trend.flow_metrics import q347_thresholds

    flow = data.daily["discharge_vol"]
    return {"mean": float(flow.mean()), "median": float(flow.median()),
            "q347": float(q347_thresholds(data.daily).iloc[0])}


def requirement_by_month(data: RiverData, occupation: Occupation) -> list[float]:
    """The imaginary requirement of each calendar month, in m³/s."""
    reference = flow_reference(data)
    base = reference["median"] if occupation.requirement_base == "median" else reference["q347"]
    return [base + share * reference["mean"] for share in occupation.requirement_share]


def _year_exposure(data: RiverData, requirement: list[float], year: int) -> dict:
    """How one calendar year compares with the requirement, day by day."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    rows = data.daily[data.daily["date"].dt.year == year]
    flow = rows.set_index("date")["discharge_vol"].reindex(days).to_numpy(dtype=float)
    need = np.take(requirement, days.month.to_numpy() - 1)
    valid = np.isfinite(flow)
    below = valid & (flow < need)  # equal to the requirement counts as meeting it

    periods, longest, longest_start, run_start = 0, 0, None, None
    for i, short in enumerate(np.append(below, False)):
        if short and run_start is None:
            run_start = i
        elif not short and run_start is not None:
            periods += 1
            if i - run_start > longest:
                longest, longest_start = i - run_start, days[run_start]
            run_start = None

    missing = np.where(below, need - flow, 0.0)
    # The (at most four) calendar months that hold the most days below the requirement.
    per_month = pd.Series(days.month[below]).value_counts()
    worst_months = sorted(int(m) for m in per_month.index[:4])
    return {
        "days_valid": int(valid.sum()),
        "days_in_year": len(days),
        "days_below": int(below.sum()),
        "periods": periods,
        "longest_days": longest,
        "longest_start": longest_start.strftime("%d %b").lstrip("0") if longest_start is not None else None,
        "deficit_hm3": float(missing.sum() * SECONDS_PER_DAY / 1e6),
        "months": worst_months,
    }


def _record_exposure(data: RiverData, requirement: list[float]) -> dict:
    """Days below the requirement in every well-covered year, and whether that number is changing."""
    from mountain_water.trend import trends

    daily = data.daily
    need = np.take(requirement, daily["date"].dt.month.to_numpy() - 1)
    valid = daily["discharge_vol"].notna().to_numpy()
    below = valid & (daily["discharge_vol"].to_numpy(dtype=float) < need)
    per_year = pd.DataFrame({"year": daily["date"].dt.year.to_numpy(), "valid": valid, "below": below}).groupby("year").sum()

    years, values = [], []
    for year in data.years:
        days_in_year = 366 if calendar.isleap(year) else 365
        covered = year in per_year.index and per_year.at[year, "valid"] >= YEAR_COVERAGE * days_in_year
        years.append(year)
        values.append(int(per_year.at[year, "below"]) if covered else None)

    numbers = np.array([np.nan if v is None else v for v in values], dtype=float)
    slope, _ = trends.sen_slope(np.array(years, dtype=float), numbers)
    p = trends.mann_kendall_p(numbers)
    usable = [y for y, v in zip(years, values) if v is not None]
    if not usable or not wording.is_number(slope):
        sentence = "There are too few complete years to say whether this is changing."
    else:
        verdict = "a statistically significant trend" if wording.is_number(p) and p < ALPHA else "not a statistically significant trend"
        sentence = (
            f"From {usable[0]} to {usable[-1]} the number of days below the requirement changed by "
            f"{wording.signed(slope * 10)} days per decade, {verdict} ({wording.p_value(p)})."
        )
    return {"years": years, "days_below": values, "sentence": sentence}


def _changes(data: RiverData, occupation: Occupation) -> list[dict]:
    """Long-term change of the yearly metrics that matter most for this occupation (trend section)."""
    from mountain_water.trend.flow_metrics import doy_to_date_label
    from mountain_water.trend.registry import info

    rows = []
    for metric in occupation.focus_metrics:
        meta = info(metric)
        unit = "" if meta.unit == "-" else meta.unit
        trend = data.trends[data.trends["metric"] == metric]
        if trend.empty:
            rows.append({"label": meta.label, "description": meta.description, "usual": "—",
                         "change": "not enough years", "evidence": "", "significant": False})
            continue
        t = trend.iloc[0]
        slope, percent, p = float(t["slope_per_decade"]), float(t["pct_per_decade"]), float(t["p"])
        if unit.startswith("day of"):  # a date: report the shift in days and the usual calendar date
            direction = " (earlier)" if slope < 0 else " (later)" if slope > 0 else ""
            change = f"{wording.signed(slope)} days per decade{direction}"
            usual = doy_to_date_label(float(t["mean"]), HYDRO_YEAR_START_MONTH).lstrip("0")
        else:
            change = (f"{wording.signed(percent)} % per decade" if wording.is_number(percent)
                      else f"{wording.signed(slope, unit)} per decade")
            usual = wording.number(float(t["mean"]), unit)
        significant = wording.is_number(p) and p < ALPHA
        rows.append({
            "label": meta.label, "description": meta.description, "usual": usual, "change": change,
            "evidence": ("significant, " if significant else "not significant, ") + wording.p_value(p),
            "significant": significant,
        })
    return rows


def _plane_points(annual: pd.DataFrame, trend_rows: pd.DataFrame) -> dict[str, dict]:
    """Quantity change, timing change and variability of each river in the tables."""
    from mountain_water.trend.variability import interannual_cv

    quantity = trend_rows[trend_rows["metric"] == QUANTITY_METRIC].set_index("gauge_id")["pct_per_decade"]
    timing = trend_rows[trend_rows["metric"] == TIMING_METRIC].set_index("gauge_id")["slope_per_decade"]
    spread = interannual_cv(annual.assign(period="all"), QUANTITY_METRIC, window_col="period")
    spread = spread.set_index("gauge_id")[f"{QUANTITY_METRIC}_interannual_cv"] * 100
    points = {}
    for river_id in quantity.index.intersection(timing.index).intersection(spread.index):
        x, y, z = float(quantity[river_id]), float(timing[river_id]), float(spread[river_id])
        if all(wording.is_number(v) for v in (x, y, z)):
            points[river_id] = {"x": x, "y": y, "z": z}
    return points


def _plane(data: RiverData) -> dict:
    """The volatility plane: where this river sits, and the other measured rivers for comparison."""
    own = _plane_points(data.annual, data.trends).get(data.river.id)
    others = []
    measured = data_source.all_measured()
    if data.river.measured and measured is not None:
        if "measured" not in _plane_cache:
            _plane_cache["measured"] = _plane_points(measured.annual, measured.trends)
        names = {r.id: f"{r.name}, {r.place}" for r in measured.rivers}
        others = [{"name": names.get(rid, rid), **point}
                  for rid, point in _plane_cache["measured"].items() if rid != data.river.id]
    return {
        "point": own,
        "others": others,
        "axes": {
            "x": "Quantity change (% per decade)",
            "y": "Timing change (days per decade)",
            "z": "Year-to-year variation (%)",
        },
        "text": None if own is None else (
            f"Yearly volume {wording.signed(own['x'])} % per decade. "
            f"Half of the year's water passes {wording.number(abs(own['y']))} days "
            f"{'earlier' if own['y'] < 0 else 'later'} per decade. "
            f"Yearly volume varies by {wording.number(own['z'])} % from year to year."
        ),
    }


def _requirement_summary(values: list[float]) -> str:
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return f"at least {wording.number(low, 'm³/s')} all year"
    return f"at least {wording.number(low, 'm³/s')} to {wording.number(high, 'm³/s')}, depending on the month"


def _year_sentence(year: int, e: dict) -> str:
    if e["days_valid"] == 0:
        return f"There are no flow measurements for {year}."
    gaps = e["days_in_year"] - e["days_valid"]
    covered = f"{e['days_valid']} measured days" if gaps else f"{e['days_valid']} days"
    if e["days_below"] == 0:
        return f"In {year} the flow met this requirement on all {covered}."
    sentence = (
        f"In {year} the flow was below this requirement on {e['days_below']} of {covered}, "
        f"in {wording.plural(e['periods'], 'period')}. The longest lasted {wording.plural(e['longest_days'], 'day')}, "
        f"from {e['longest_start']}. In total {wording.number(e['deficit_hm3'])} million m³ were missing, "
        f"mostly in {wording.month_list(e['months'])}."
    )
    return sentence + (f" {wording.plural(gaps, 'day')} had no measurement." if gaps else "")


def assess(data: RiverData, occupation: Occupation, year: int, predicted_flow: list[float | None] | None) -> dict:
    """Everything the risk section shows. ``predicted_flow`` is given for the prediction year only."""
    requirement = requirement_by_month(data, occupation)
    result = {
        "occupation": {"id": occupation.id, "label": occupation.label, "question": occupation.question},
        "requirement": {
            "name": occupation.requirement_name,
            "summary": _requirement_summary(requirement),
            "text": occupation.requirement_text,
            "values": requirement,
            "unit": "m³/s",
            "imaginary": True,
        },
        "record": _record_exposure(data, requirement),
        "changes": _changes(data, occupation),
        "plane": _plane(data),
        "scores": imaginary.scores(f"{data.river.id}|{occupation.id}|{year}"),
        "needs": list(occupation.needs),
        "imaginary_river": not data.river.measured,
    }
    if predicted_flow is None:
        exposure = _year_exposure(data, requirement, year)
        result["year"] = {
            "sentence": _year_sentence(year, exposure),
            "facts": [
                {"label": "Days below", "value": f"{exposure['days_below']}", "of": f"of {exposure['days_valid']}"},
                {"label": "Shortfall periods", "value": f"{exposure['periods']}", "of": ""},
                {"label": "Longest", "value": f"{exposure['longest_days']}", "of": "days"},
                {"label": "Missing water", "value": wording.number(exposure["deficit_hm3"]), "of": "million m³"},
            ],
        }
    else:
        short = [m + 1 for m, (flow, need) in enumerate(zip(predicted_flow, requirement))
                 if flow is not None and flow < need]
        sentence = (f"In the imaginary prediction for {year}, the monthly flow stays above the requirement all year."
                    if not short else
                    f"In the imaginary prediction for {year}, {wording.plural(len(short), 'month')} "
                    f"{'falls' if len(short) == 1 else 'fall'} below the requirement: {wording.month_list(short)}.")
        result["year"] = {
            "sentence": sentence + " A monthly prediction cannot show shortfalls shorter than a month.",
            "facts": [{"label": "Months below", "value": f"{len(short)}", "of": "of 12"}],
        }
    return result
