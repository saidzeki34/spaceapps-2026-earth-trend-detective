"""Station x month view on the synthetic CAMELS-CH layout. Values are invented; only the structure matters."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import write_fake_camels

from mountain_water.trend import plots, stations
from mountain_water.trend.settings import StationNetworkSettings

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
    s = StationNetworkSettings(raw_dir=raw_dir, processed_dir=tmp_path_factory.mktemp("stations"), n_gauges=3)
    return stations.build(s)


def test_selection_ranks_complete_swiss_streams_by_elevation(network):
    # 2006 is Austrian, 2003 has a gap, 2007 a long gap; 2004 (2500 m) > 2001 (2200 m) > 2002 (1900 m) > 2005.
    assert network.gauges == ["2004", "2001", "2002"]
    assert network.selection_log["remaining"].tolist() == [7, 6, 6, 6, 4, 3]
    assert network.stations["label"].iloc[0] == "Testbach – Testbach 2004 (2004) · 2,500 m"


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


def test_leap_day_left_out():
    dates = pd.date_range("2004-01-01", "2004-12-31")
    daily = pd.DataFrame({"gauge_id": "x", "date": dates, "discharge_vol": 1.0})
    a = stations.annual_metrics(daily).iloc[0]
    assert a["m02"] == pytest.approx(28 * stations.HM3_PER_M3S_DAY)
    assert a["annual_hm3"] == pytest.approx(365 * stations.HM3_PER_M3S_DAY)


def test_trends_relative_to_baseline(network):
    t = network.trends
    assert len(t) == 3 * len(stations.METRICS)
    annual = t[t["metric"] == "annual_hm3"].set_index("gauge_id")
    # The fixture scales flow by (1 - 0.02 per decade): about -2 % of the 1981-2000 mean per decade.
    assert annual["change_per_decade"].between(-3, -1).all()
    timing = t[t["metric"] == "half_volume_doy"].set_index("gauge_id")["change_per_decade"]
    assert timing["2004"] < timing["2002"] < 0  # peak moves 8 vs 3 days earlier per decade
    s = stations.summary(network)
    assert s.set_index("metric").loc["annual_hm3", "n_negative"] == 3


def test_saved_network_roundtrip_and_tables(network):
    loaded = stations.load(StationNetworkSettings(processed_dir=network.meta["settings"]["processed_dir"]).processed_dir)
    assert loaded.gauges == network.gauges
    wide = stations.wide_table(network)
    assert wide["gauge_id"].tolist() == network.gauges
    assert "Jul (% of baseline per decade)" in wide and "Half-volume date (days per decade)" in wide
    anomalies = stations.year_anomalies(network)
    base = anomalies[anomalies["year"].between(1981, 2000)].groupby("gauge_id")["half_volume_days"].mean()
    assert np.allclose(base, 0)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_figures(network, theme):
    fig = plots.station_month_heatmap(network, theme=theme)
    assert [np.asarray(tr.z).shape for tr in fig.data] == [(3, 12), (3, 3), (3, 1)]
    assert list(fig.data[0].y) == network.stations["label"].tolist()
    fig = plots.station_year_heatmaps(network, theme=theme)
    assert [np.asarray(tr.z).shape for tr in fig.data] == [(3, 40), (3, 40)]


def test_baseline_outside_period_rejected():
    with pytest.raises(ValueError):
        StationNetworkSettings(baseline=(1970, 1990))
