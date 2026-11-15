"""Norway (NVE) pipeline against fake HydAPI / ArcGIS / GTS services. Values are synthetic."""

import json

import numpy as np
import pandas as pd
import pytest

from mountain_water.trend import gldas, nve, pipeline, plots, sources
from mountain_water.trend.settings import CatchmentFilter, TrendSettings

from conftest import FakeGiovanni

START, END = "1990-10-01", "2012-09-30"

# stationId, polygon id as in the map layer, lat, lon, median elevation, area, regulation, first year, timing shift
STATIONS = [
    ("2.11.0", "2.11", 61.50, 8.40, 1100, 120, 0, 1960, -5.0),
    ("2.32.0", "2.32", 61.80, 9.20, 900, 300, 0, 1960, -2.0),
    ("12.70.0", "12.70", 60.60, 7.60, 1300, 60, 0, 1960, -8.0),
    ("6.10.0", "6.10", 60.20, 11.10, 400, 200, 0, 1960, 0.0),     # too low
    ("16.66.0", "16.66", 59.90, 8.00, 1000, 200, 50, 1960, 0.0),  # regulated
    ("72.77.0", "72.77", 63.10, 11.50, 950, 80, 0, 2005, 0.0),    # too short
]


class FakeNve:
    def __init__(self):
        self.calls = {"discharge": 0, "senorge": 0}

    def stations(self):
        out = []
        for sid, _, lat, lon, elev, area, reg, first, _ in STATIONS:
            out.append({
                "stationId": sid, "stationName": f"Testelv {sid}", "riverName": "Testelva",
                "latitude": lat, "longitude": lon, "drainageBasinArea": area, "heightHypso50": elev,
                "percentGlacier": 2.5, "reservoirVolumeIn": reg or None,
                "seriesList": [{"parameter": 1001, "parameterName": "Vannføring", "resolutionList": [
                    {"resTime": 0, "dataFromTime": f"{first}-01-01T00:00:00Z", "dataToTime": None},
                    {"resTime": 1440, "dataFromTime": f"{first}-01-01T00:00:00Z", "dataToTime": None}]}],
            })
        return out

    def discharge(self, sid, start, end):
        self.calls["discharge"] += 1
        row = next(s for s in STATIONS if s[0] == sid)
        local = pd.date_range(max(start, f"{row[7]}-01-01"), end, freq="D", tz="Europe/Oslo")
        doy = local.day_of_year.to_numpy()
        decades = (local.year.to_numpy() - 1990) / 10
        rng = np.random.default_rng(len(sid))
        q = row[5] / 50 * (0.3 + 3 * np.exp(-0.5 * ((doy - (165 + row[8] * decades)) / 25) ** 2))
        q *= np.exp(rng.normal(0, 0.1, len(q)))
        obs = [{"time": t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "value": float(v), "quality": 2}
               for t, v in zip(local, q)]
        obs[100]["value"] = None
        return {"data": [{"stationId": sid, "parameter": 1001, "observations": obs}]}

    def catchment_page(self, offset, page_size=1000):
        from pyproj import Transformer

        to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
        feats = []
        for _, pid, lat, lon, _, area, *_ in STATIONS if offset == 0 else []:
            x, y = to_utm.transform(lon, lat)
            h = (area * 1e6) ** 0.5 / 2
            ring = [[x - h, y - h], [x - h, y + h], [x + h, y + h], [x + h, y - h], [x - h, y - h]]
            feats.append({"type": "Feature", "properties": {"STASJON_NR": pid, "AREAL_KM2": area},
                          "geometry": {"type": "Polygon", "coordinates": [ring]}})
        return {"type": "FeatureCollection", "features": feats}

    def senorge(self, theme, rings, start, end):
        self.calls["senorge"] += 1
        assert rings and len(rings[0]) >= 4
        d = pd.date_range(start, end, freq="D")
        doy = d.day_of_year.to_numpy()
        years = (d.year.to_numpy() - 1990) / 10
        rng = np.random.default_rng(len(theme))
        values = {
            "rr": rng.gamma(0.7, 4, len(d)),
            "tm": -1 + 9 * np.sin(2 * np.pi * (doy - 110) / 365) + 0.35 * years + rng.normal(0, 2, len(d)),
            "swe": np.clip(300 * np.cos(2 * np.pi * (doy - 75) / 365), 0, None),
        }[theme]
        values = np.round(values, 2).tolist()
        values[3] = 65535
        return {"Theme": theme, "NoDataValue": 65535, "TimeResolution": 1440, "Unit": "mm", "Data": values}


@pytest.fixture(scope="module")
def nve_setup(tmp_path_factory):
    raw = tmp_path_factory.mktemp("nve_raw")
    client = FakeNve()
    log = nve.download(raw, start=START, end=END, min_years=15, chunk_years=10, workers=2, client=client)
    s = TrendSettings.nve(nve_raw_dir=raw, processed_dir=tmp_path_factory.mktemp("nve_processed"))
    s.filters.min_valid_years = 15
    return dict(raw=raw, client=client, log=log, results=pipeline.build_nve(s), settings=s)


def test_station_attributes_and_candidates():
    attrs = nve.station_attributes(FakeNve().stations())
    assert attrs.set_index("gauge_id").loc["16.66.0", "regulated"] == 1
    assert attrs.set_index("gauge_id").loc["2.11.0", "regulated"] == 0
    cands = nve.candidate_stations(attrs, 800, 500, 15, START, END)
    assert sorted(cands["gauge_id"]) == ["12.70.0", "2.11.0", "2.32.0"]


def test_parse_discharge_uses_local_dates():
    payload = {"data": [{"observations": [
        {"time": "1999-12-31T23:00:00Z", "value": 1.5, "quality": 2},   # 2000-01-01 00:00 CET
        {"time": "2000-06-30T22:00:00Z", "value": None, "quality": 0},  # 2000-07-01 00:00 CEST
    ]}]}
    q = nve.parse_discharge(payload)
    assert q["date"].dt.strftime("%Y-%m-%d").tolist() == ["2000-01-01", "2000-07-01"]
    assert np.isnan(q["discharge_vol"].iloc[1])


def test_parse_senorge_nodata():
    s = nve.parse_senorge({"Data": [1, 65535, 3], "NoDataValue": 65535, "TimeResolution": 1440}, "2001-01-01")
    assert np.isnan(s.iloc[1]) and s.index[2] == pd.Timestamp("2001-01-03")
    with pytest.raises(ValueError):
        nve.parse_senorge({"Data": [1], "TimeResolution": 60}, "2001-01-01")


def test_download_only_candidates_and_resumes(nve_setup):
    raw, client, log = nve_setup["raw"], nve_setup["client"], nve_setup["log"]
    assert (log["error"] == "").all()
    assert sorted(p.stem for p in (raw / "discharge").glob("*.json")) == ["12.70.0", "2.11.0", "2.32.0"]
    polygons, _ = nve.load_catchments(raw, ["2.11.0"])  # "2.11" in the layer matches "2.11.0"
    assert polygons["2.11.0"].area / 1e6 == pytest.approx(120, rel=1e-3)
    before = dict(client.calls)
    again = nve.download(raw, start=START, end=END, min_years=15, chunk_years=10, client=client)
    assert again.empty and client.calls == before


def test_nve_pipeline(nve_setup):
    r = nve_setup["results"]
    assert r.meta["source"] == "nve" and r.gauges == ["12.70.0", "2.11.0", "2.32.0"]
    assert r.meta["windows"][0] == "1991-2000"
    steps = r.selection_log.set_index("step")["remaining"]
    assert steps.iloc[0] == 6 and steps.iloc[-1] == 3
    a = r.annual
    assert {"precip_total_mm", "temp_mean", "swe_max_mm", "runoff_mm"} <= set(a.columns)
    assert a["runoff_mm"].gt(0).all()
    t = r.trends.set_index(["gauge_id", "metric"])
    assert t.loc[("12.70.0", "com_doy"), "slope_per_decade"] < -3
    assert t.loc[("12.70.0", "temp_mean"), "slope_per_decade"] > 0
    assert len(plots.regime_by_window(r, "12.70.0").data) and len(plots.trend_map(r, "com_doy").data)


def test_gldas_for_norway(nve_setup, tmp_path_factory):
    s_obs = nve_setup["settings"]
    s = TrendSettings.gldas("no", nve_raw_dir=s_obs.nve_raw_dir, gldas_raw_dir=tmp_path_factory.mktemp("g_raw"),
                            processed_dir=tmp_path_factory.mktemp("g_no"), window_years=5, min_window_years=3,
                            filters=CatchmentFilter(min_valid_years=8))
    gauges = nve_setup["results"].gauges
    _, weights = pipeline.gldas_inputs("no", gauges, s)
    assert set(weights["gauge_id"]) == set(gauges) and np.allclose(weights.groupby("gauge_id")["weight"].sum(), 1)
    gldas.download(weights, s.gldas_raw_dir, start="2000-01-01", end="2012-12-31", client=FakeGiovanni(), workers=2)
    g = pipeline.build_gldas(s, gauges, region="no")
    assert g.meta["region"] == "no" and g.gauges == gauges
    cmp = sources.compare_annual(nve_setup["results"], g, min_years=5)
    assert set(cmp["gauge_id"]) == set(gauges)
    assert len(plots.source_regime(nve_setup["results"], g, "2.11.0").data) == 2
