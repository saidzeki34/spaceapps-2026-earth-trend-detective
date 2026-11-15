"""Station x month view on the synthetic CAMELS-CH layout and fake NVE services. Values are invented."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import write_fake_camels
from test_nve import END, START, FakeNve

from mountain_water.trend import nve, pipeline, plots, stations
from mountain_water.trend.settings import StationNetworkSettings, TrendSettings

# gauge -> (country, water body type); 2005 is lowest, 2007 has a long gap
LOCATION = {
    "2001": ("CH", "stream"), "2002": ("CH", "stream"), "2003": ("CH", "stream"), "2004": ("CH", "stream"),
    "2005": ("CH", "stream"), "2006": ("A", "stream"), "2007": ("CH", "stream"),
}


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory):
    """Fake CAMELS-CH where the scattered one-day gaps are filled, except one gap left at 2003."""
    raw = tmp_path_factory.mktemp("stations_raw")
    base = write_fake_camels(raw)
    obs_dir = base / "timeseries" / "observation_based"
    for path in obs_dir.glob("*.csv"):
        df = pd.read_csv(path)
        col = "discharge_vol(m3/s)"
        if not path.stem.endswith("2007"):
            df[col] = df[col].interpolate(limit_direction="both")
        if path.stem.endswith("2003"):
            df.loc[5000, col] = np.nan
        df.to_csv(path, index=False)
    pd.DataFrame({"gauge_id": list(LOCATION), "country": [c for c, _ in LOCATION.values()],
                  "water_body_type": [w for _, w in LOCATION.values()]}).to_csv(
        base / "static_attributes" / "CAMELS_CH_location_attributes.csv", index=False)
    return raw


@pytest.fixture(scope="module")
def network(raw_dir, tmp_path_factory):
    s = StationNetworkSettings(regions=("ch",), raw_dir=raw_dir, processed_dir=tmp_path_factory.mktemp("stations"),
                               n_gauges=3)
    return stations.build(s)


@pytest.fixture(scope="module")
def build_both(raw_dir, tmp_path_factory):
    """Builds Switzerland + Norway over the fake NVE period (complete calendar years 1992-2011 in Norway)."""
    nve_raw = tmp_path_factory.mktemp("stations_nve_raw")
    nve.download(nve_raw, start=START, end=END, min_years=15, workers=2, client=FakeNve())
    nve_settings = TrendSettings.nve(nve_raw_dir=nve_raw, processed_dir=tmp_path_factory.mktemp("stations_nve_sel"))
    nve_settings.filters.min_valid_years = 15
    pipeline.build_nve(nve_settings)

    def build(**overrides):
        kw = dict(raw_dir=raw_dir, nve_raw_dir=nve_raw, nve_selection_dir=nve_settings.processed_dir,
                  processed_dir=tmp_path_factory.mktemp("stations_both"), n_gauges=3, first_year=1991,
                  last_year=2011, baseline=(1991, 2000), min_complete_years=15, min_baseline_years=5,
                  min_paired_years=10)
        return stations.build(StationNetworkSettings(**(kw | overrides)))
    return build


def test_selection_ranks_complete_swiss_streams_by_elevation(network):
    # 2006 is Austrian, 2003 has a gap, 2007 a long gap; 2004 (2500 m) > 2001 (2200 m) > 2002 (1900 m) > 2005.
    assert network.gauges == ["2004", "2001", "2002"]
    assert network.selection_log["remaining"].tolist() == [7, 6, 6, 6, 4, 3, 3]
    assert network.stations["label"].iloc[0] == "Testbach – Testbach 2004 (2004) · 2,500 m"
    assert network.stations["sufficient"].all() and (network.stations["complete_years"] == 40).all()


def test_annual_metrics_volumes_and_half_volume_date():
    dates = pd.date_range("2001-01-01", "2001-12-31")
    flow = np.where(dates.month == 7, 10.0, 1.0)  # July carries most of the volume
    daily = pd.DataFrame({"gauge_id": "x", "date": dates, "discharge_vol": flow})
    a = stations.annual_metrics(daily).iloc[0]
    assert a["m07"] == pytest.approx(31 * 10 * stations.HM3_PER_M3S_DAY)
    assert a["annual_hm3"] == pytest.approx((334 + 310) * stations.HM3_PER_M3S_DAY)
    assert a["aug_sep_hm3"] == pytest.approx(61 * stations.HM3_PER_M3S_DAY)
    assert a["aug_sep_min7"] == pytest.approx(1.0)
    # half of 644 units = 322; 181 units by 30 June, then 10 per day -> day 181 + 15 = 196 (15 July)
    assert a["half_volume_doy"] == 196


def test_incomplete_years_are_left_out():
    dates = pd.date_range("2001-01-01", "2002-12-31")
    daily = pd.DataFrame({"gauge_id": "x", "date": dates, "discharge_vol": 1.0})
    daily.loc[400, "discharge_vol"] = np.nan  # one missing day in 2002
    assert stations.annual_metrics(daily)["year"].tolist() == [2001]


def test_leap_day_left_out():
    dates = pd.date_range("2004-01-01", "2004-12-31")
    daily = pd.DataFrame({"gauge_id": "x", "date": dates, "discharge_vol": 1.0})
    a = stations.annual_metrics(daily).iloc[0]
    assert a["m02"] == pytest.approx(28 * stations.HM3_PER_M3S_DAY)
    assert a["annual_hm3"] == pytest.approx(365 * stations.HM3_PER_M3S_DAY)


def test_snow_free_date_ignores_september_reset():
    doy = np.arange(1, 366)
    melting = pd.Series(np.clip(200 - 2 * np.abs(doy - 90), 0, None), dtype=float)  # peak day 90, gone by day 190
    assert stations._snow_free_day(melting, 10) == pytest.approx(185)  # first day <= 5 % of 200 mm
    stuck = pd.Series(np.where(doy < 245, 100.0, 0.0))  # never melts, reset to 0 on 2 September
    assert np.isnan(stations._snow_free_day(stuck, 10))
    assert np.isnan(stations._snow_free_day(melting / 100, 10))  # peak below the minimum


def test_trends_relative_to_baseline(network):
    t = network.trends
    assert len(t) == 3 * len(stations.METRICS)
    annual = t[t["metric"] == "annual_hm3"].set_index("gauge_id")
    # The fixture scales flow by (1 - 0.02 per decade): about -2 % of the 1981-2000 mean per decade.
    assert annual["change_per_decade"].between(-3, -1).all()
    area = network.stations.set_index("gauge_id")["area"]
    assert np.allclose(annual["runoff_change_per_decade"], annual["slope_per_decade"] * 1000 / area[annual.index])
    timing = t[t["metric"] == "half_volume_doy"].set_index("gauge_id")["change_per_decade"]
    assert timing["2004"] < timing["2002"] < 0  # peak moves 8 vs 3 days earlier per decade
    s = stations.summary(network)
    assert s.set_index("metric").loc["annual_hm3", "n_negative"] == 3


def test_saved_network_roundtrip_and_tables(network):
    loaded = stations.load(Path(network.meta["settings"]["processed_dir"]))
    assert loaded.gauges == network.gauges
    wide = stations.wide_table(network)
    assert wide["gauge_id"].tolist() == network.gauges
    assert {"Jul (% of baseline per decade)", "Jul (mm per decade)", "Half-volume date (days per decade)"} <= set(wide)
    anomalies = stations.year_anomalies(network)
    base = anomalies[anomalies["year"].between(1981, 2000)].groupby("gauge_id")["half_volume_days"].mean()
    assert np.allclose(base, 0)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_figures(network, theme):
    fig = plots.station_month_heatmap(network, theme=theme)
    shapes = [np.asarray(tr.z).shape for tr in fig.data]
    assert shapes == [(3, 12), (3, 12), (3, 3), (3, 3), (3, 1), (3, 1)]  # grey layer + values per column group
    assert list(fig.data[1].y) == network.stations["label"].tolist()
    fig = plots.station_year_heatmaps(network, theme=theme)
    assert [np.asarray(tr.z).shape for tr in fig.data] == [(3, 40)] * 4


def test_switzerland_and_norway(build_both):
    net = build_both()
    assert net.countries == ["Switzerland", "Norway"]
    no = net.stations[net.stations["country"] == "Norway"]
    assert no["gauge_id"].tolist() == ["12.70.0", "2.11.0", "2.32.0"]  # median elevation 1300 > 1100 > 900 m
    assert no["rank"].tolist() == [1, 2, 3] and (no["elevation_statistic"] == "median").all()
    # One missing day in January 1991 leaves 1992-2011 complete.
    assert (no["complete_years"] == 20).all() and (no["baseline_years"] == 9).all() and no["sufficient"].all()
    t = net.trends.set_index(["gauge_id", "metric"])
    assert t.loc[("12.70.0", "half_volume_doy"), "change_per_decade"] < -3  # peak moves 8 days earlier per decade
    snow = net.annual.loc[net.annual["gauge_id"].isin(no["gauge_id"]), "snow_free_doy"]
    assert snow.between(150, 175).all()
    d = stations.driver_changes(net)
    assert set(d.loc[d["country"] == "Norway", "flow"]) == {"half_volume_doy", "aug_sep_min7"}
    s = stations.summary(net)
    assert set(s["country"]) == {"Switzerland", "Norway"}

    fig = plots.station_month_heatmap(net)
    assert len(fig.data) == 12  # 2 countries x 3 column groups x (grey layer + values)
    assert len(plots.driver_change_scatter(net, "aug_sep_min7", "precip_jul_sep_mm").data) == 2
    assert len(plots.station_year_heatmaps(net).data) == 8


def test_short_records_get_no_slope(build_both):
    net = build_both(min_complete_years=21)  # Switzerland has 21 complete years, Norway 20
    st = net.stations.set_index("gauge_id")
    assert st.groupby("country")["sufficient"].all().to_dict() == {"Norway": False, "Switzerland": True}
    t = net.trends.merge(net.stations[["gauge_id", "country"]].rename(columns={"country": "c"}), on="gauge_id")
    assert t.loc[t["c"] == "Norway", "change_per_decade"].isna().all()
    assert t.loc[t["c"] == "Switzerland", "change_per_decade"].notna().all()
    grey = plots.station_month_heatmap(net).data[6]  # Norway, month columns, grey layer
    assert np.isfinite(np.asarray(grey.z, dtype=float)).all()


def test_settings_rejected():
    with pytest.raises(ValueError):
        StationNetworkSettings(baseline=(1970, 1990))
    with pytest.raises(ValueError):
        StationNetworkSettings(regions=("se",))
