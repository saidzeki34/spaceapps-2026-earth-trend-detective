import pandas as pd

from mountain_water.trend import camels_ch, preprocessing
from mountain_water.trend.settings import CatchmentFilter


def test_split_header():
    assert camels_ch.split_header("discharge_vol(m3/s)") == ("discharge_vol", "m3/s")
    assert camels_ch.split_header("swe (mm)") == ("swe", "mm")
    assert camels_ch.split_header("date") == ("date", None)


def test_load_observed_and_attributes(fake_raw_dir):
    root = camels_ch.find_dataset_root(fake_raw_dir)
    obs, units = camels_ch.load_observed(root, ["2001", "2002"])
    assert set(obs["gauge_id"]) == {"2001", "2002"}
    assert units["discharge_vol"] == "m3/s"
    assert pd.api.types.is_datetime64_any_dtype(obs["date"])
    attrs = camels_ch.load_attributes(root)  # one table has a comment line and ';' separator
    assert {"elev_mean", "num_reservoir", "gauge_lat"} <= set(attrs.columns)
    assert len(attrs) == 7
    assert "Observed series files: 7" in camels_ch.describe(root)


def test_hydro_year_labels_by_end_year():
    df = pd.DataFrame({"date": pd.to_datetime(["2019-09-30", "2019-10-01", "2020-09-30"])})
    out = preprocessing.add_hydro_year(df, 10)
    assert out["hydro_year"].tolist() == [2019, 2020, 2020]
    assert out["hydro_doy"].tolist() == [365, 1, 366]


def test_fill_short_gaps_only():
    values = [1.0, None, None, 4.0] + [5.0] + [None] * 7 + [13.0]
    df = pd.DataFrame({"gauge_id": "a", "date": pd.date_range("2000-01-01", periods=len(values)), "q": values})
    out = preprocessing.fill_short_gaps(df, ["q"], max_gap=5)
    assert out["q"].iloc[1] == 2.0 and out["q_filled"].iloc[1]
    assert out["q"].iloc[5:12].isna().all()


def test_windows_ten_year_steps():
    assert preprocessing.windows(range(1982, 2021), 10, 8) == [(1982, 1991), (1992, 2001), (2002, 2011), (2012, 2020)]
    assert preprocessing.windows(range(1981, 2021), 10, 8)[-1] == (2011, 2020)
    assert preprocessing.windows(range(1981, 1996), 10, 8) == [(1981, 1990)]  # short tail dropped


def test_select_catchments_skips_missing_columns():
    attrs = pd.DataFrame({"gauge_id": ["a", "b"], "elev_mean": [2000, 900]})
    comp = pd.DataFrame({"gauge_id": ["a"] * 30 + ["b"] * 30, "hydro_year": list(range(30)) * 2, "completeness": 1.0})
    gauges, log = preprocessing.select_catchments(attrs, comp, CatchmentFilter(), 0.9)
    assert gauges == ["a"]
    assert log["step"].str.contains("SKIPPED").sum() == 2  # no area / reservoir columns
