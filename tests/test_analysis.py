from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mountain_water.analysis.baseline import build_baseline
from mountain_water.analysis.flow_metrics import (
    calculate_flow_metrics,
    interval_volume,
    period_summaries,
)
from mountain_water.analysis.risk import assess_threshold_exposure
from mountain_water.analysis.trends import estimate_trend
from mountain_water.analysis.variability import calculate_variability
from mountain_water.contracts import RequirementSeries


def requirement(table, value):
    return RequirementSeries(pd.DataFrame({"start": [table.start.min()], "end": [table.end.max()],
        "requirement_m3s": [value]}), "test", "test user", "synthetic scenario")


def test_volume_units_and_missing_not_zero(flow_factory):
    flow = flow_factory([1, 0, np.nan])
    volume = interval_volume(flow.table)
    assert volume.iloc[0] == 86400
    assert volume.iloc[1] == 0
    assert np.isnan(volume.iloc[2])
    result = calculate_flow_metrics(flow.table, flow.table.start.min(), flow.table.end.max())
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["observed_volume_m3"] == 86400
    assert result["complete_volume_m3"] is None


def test_equality_and_time_varying_requirements(flow_factory):
    t = flow_factory([1, 1]).table
    r = RequirementSeries(pd.DataFrame({"start": t.start, "end": t.end, "requirement_m3s": [1, 2]}),
                          "changing", "test", "synthetic")
    result = assess_threshold_exposure(t, r, 172800)
    assert result["deficit_volume_m3"] == 86400
    assert result["below_fraction"] == .5
    assert result["events"][0]["start"] == t.start.iloc[1].isoformat()
    assert result["events"][0]["start_censored"] is False


def test_finer_requirement_is_unresolved(flow_factory):
    t = flow_factory([1]).table
    middle = t.start.iloc[0] + pd.Timedelta(hours=12)
    r = RequirementSeries(pd.DataFrame({"start": [t.start.iloc[0], middle],
        "end": [middle, t.end.iloc[0]], "requirement_m3s": [0, 2]}), "within-day", "test", "synthetic")
    result = assess_threshold_exposure(t, r, 86400)
    assert result["assessed_seconds"] == 0
    assert result["deficit_volume_m3"] is None
    assert result["unresolved_requirement_intervals"] == 1


@pytest.mark.parametrize("missing_row", [True, False])
def test_gaps_break_and_censor_events(flow_factory, missing_row):
    t = flow_factory([0, 0, np.nan, 0, 1]).table
    if missing_row:
        t = t.drop(index=2)
    result = assess_threshold_exposure(t, requirement(t, 1), 5 * 86400)
    assert result["event_count"] == 2
    assert result["longest_event_seconds"] == 2 * 86400
    assert result["events"][0]["end_censored"] is True
    assert result["events"][1]["start_censored"] is True
    assert result["events"][1]["end_censored"] is False
    assert result["coverage"] == .8


def test_all_missing_does_not_report_zero_deficit(flow_factory):
    t = flow_factory([np.nan, np.nan]).table
    result = assess_threshold_exposure(t, requirement(t, 1), 172800)
    assert result["event_count"] is None
    assert result["deficit_volume_m3"] is None
    assert result["below_fraction"] is None


def test_complete_year_and_midpoint(flow_factory):
    flow = flow_factory(np.ones(365))
    year = period_summaries(flow, water_year_start_month=1).iloc[0]
    assert year.season_volume_m3 == 365 * 86400
    assert year.half_volume_day == 182.5
    bad = flow.table.copy()
    bad.loc[30, "valid"] = False
    year = period_summaries(replace(flow, table=bad), water_year_start_month=1).iloc[0]
    assert np.isnan(year.season_volume_m3)
    assert np.isnan(year.half_volume_day)


def test_zero_year_has_no_half_volume_day(flow_factory):
    year = period_summaries(flow_factory(np.zeros(365)), water_year_start_month=1).iloc[0]
    assert year.season_volume_m3 == 0
    assert np.isnan(year.half_volume_day)


def test_leap_year_and_water_year_assignment(flow_factory):
    period = period_summaries(flow_factory(np.ones(366), "1999-10-01")).iloc[0]
    assert period.year == 1999
    assert period.expected_days == 366
    assert period.half_volume_day == 183


def test_baseline_reference_is_separate_and_leap_day_has_own_count(flow_factory):
    dates = pd.date_range("2000-01-01", "2003-12-31")
    flow = flow_factory(np.where(dates.year < 2002, 1., 999.), "2000-01-01")
    baseline = build_baseline(flow, (2000, 2001)).set_index("day")
    assert (baseline["mean"].dropna() == 1).all()
    assert baseline.loc["02-29", "count"] == 1
    assert baseline.loc["02-28", "expected"] == 2


def test_normalised_axes_and_residual_variability():
    p = pd.DataFrame({"year": [2000, 2010, 2020], "season_volume_m3": [100., 110., 120.],
                      "half_volume_day": [10., 12., 14.]})
    v = calculate_variability(p, 100.)
    assert v["quantity_pct_decade"] == 10
    assert v["timing_days_decade"] == 2
    assert v["variability_pct"] == pytest.approx(0, abs=1e-12)
    assert calculate_variability(p, 0)["status"] == "invalid_normalisation"
    p["season_volume_m3"] = 100.
    assert calculate_variability(p, 100)["quantity_pct_decade"] == 0
    assert calculate_variability(p, 100)["variability_pct"] == 0


def test_uncertainty_requires_consecutive_annual_evidence():
    assert estimate_trend([2000, 2001, 2003], [1, 2, 4], "m3/year")["interval"] is None
    result = estimate_trend(np.arange(2000, 2025), np.arange(25) * 2., "m3/year", bootstrap_samples=99)
    assert result["slope_per_year"] == 2
    assert result["interval"] == [2, 2]
    assert result["interval_level"] == .975


def test_monthly_outlook_withholds_daily_events(flow_factory):
    t = flow_factory([0]).table
    t.loc[0, "end"] = t.start.iloc[0] + pd.Timedelta(days=31)
    result = assess_threshold_exposure(t, requirement(t, 1), 31 * 86400, allow_events=False)
    assert result["deficit_volume_m3"] == 31 * 86400
    assert result["event_count"] is None
    assert result["longest_event_seconds"] is None
