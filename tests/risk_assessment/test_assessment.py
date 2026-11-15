import numpy as np
import pandas as pd
import pytest
from mountain_water.risk_assessment.assessment import assess, daily_record, annual_metrics, fit, threshold_events


def record(first="1981-10-01", last="2020-09-30", value=10.):
    dates = pd.date_range(first, last)
    return pd.DataFrame({"date": dates, "discharge_vol": value, "discharge_vol_filled": False})


def test_constant_flow():
    out = assess(record())
    assert out["xyz_ready"]
    assert out["xyz"]["quantity_pct_decade"] == pytest.approx(0)
    assert out["xyz"]["variability_pct_baseline"] == pytest.approx(0)
    assert out["baseline_volume_m3"] == 61 * 86400 * 10
    assert out["common_years"] == 39


def test_known_volume_trend():
    d = record()
    year = d.date.dt.year + (d.date.dt.month >= 10).astype(int)
    d["discharge_vol"] = 10 + (year - 1982)
    out = assess(d)
    assert out["xyz"]["quantity_pct_decade"] == pytest.approx(1000 / 19.5)


def test_actual_year_slope():
    x = np.arange(1980, 2020, 2)
    assert fit(x, 3. * x)["slope"] == pytest.approx(3)


def test_missing_day_excludes_year():
    d = record()
    d = d[d.date != pd.Timestamp("2000-08-01")]
    out = assess(d)
    assert out["common_years"] == 38
    assert 2000 not in out["common_year_labels"]


def test_interpolated_day_excluded():
    d = record()
    d.loc[d.date == "2000-08-01", "discharge_vol_filled"] = True
    assert assess(d)["common_years"] == 38


def test_zero_baseline():
    assert not assess(record(value=0.))["xyz_ready"]


def test_missing_baseline_is_not_zero():
    out = assess(record(), baseline=(1850, 1870))
    assert out["baseline_volume_m3"] is None
    assert not out["xyz_ready"]


def test_short_record_is_unavailable():
    assert not assess(record("2005-10-01", "2010-09-30"))["xyz_ready"]


def test_leap_year_volume():
    q, _, _ = daily_record(record("1999-10-01", "2000-09-30", 1.))
    row = annual_metrics(q, list(range(1, 13)), 10).iloc[0]
    assert row.volume_m3 == 366 * 86400
    assert row.half_volume_day == 183


def test_gap_censors_events():
    q = pd.Series([3., 1., 1., np.nan, 1., 3.], index=pd.date_range("2000-01-01", periods=6))
    e = threshold_events(q, 2.)
    assert e["observed_segments"] == 2
    assert e["complete_events"] == 0
    assert e["deficit_m3"] == 3 * 86400
    assert e["below_percent"] == 60
    assert all(r["censored"] for r in e["events"])


def test_complete_episode():
    q = pd.Series([3., 1., 1., 3.], index=pd.date_range("2000-01-01", periods=4))
    e = threshold_events(q, 2.)
    assert e["median_complete_duration_days"] == 2
    assert e["above_requirement_m3"] == 2 * 86400
    assert not e["events"][0]["censored"]


def test_scenario_season_denominator():
    out = assess(record(), requirement=11.)
    assert out["exposure"]["valid_days"] == 39 * 61
    assert out["exposure"]["below_percent"] == 100
    assert out["exposure"]["deficit_m3"] == 39 * 61 * 86400
    assert out["exposure"]["missing_days"] == 0


@pytest.mark.parametrize("kwargs", [{"months":[0]}, {"period":(2020,1980)}, {"requirement":-1}, {"requirement":float("nan")}])
def test_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        assess(record(), **kwargs)


def test_duplicate_dates_rejected():
    d = record()
    with pytest.raises(ValueError):
        daily_record(pd.concat([d, d.iloc[:1]]))


def test_negative_and_infinite_are_missing():
    d = record()
    d.loc[0, "discharge_vol"] = -1
    d.loc[1, "discharge_vol"] = float("inf")
    q, _, _ = daily_record(d)
    assert q.iloc[:2].isna().all()
