import numpy as np
import pandas as pd
import pytest

from mountain_water.trend import gldas, pipeline, plots, sources
from mountain_water.trend.catchment_grid import weighted_mean

SAMPLE = """Title:,Time Series, Area-Averaged of Tair_f_inst
Fill Value (Data):,-9999.0

Timestamp (UTC),Data
2010-01-01T00:00:00,270.0
2010-01-01T03:00:00,-9999.0
2010-01-01T06:00:00Z,272.5
"""


def test_parse_timeseries():
    series, meta = gldas.parse_timeseries(SAMPLE)
    assert len(series) == 3 and np.isnan(series.iloc[1])
    assert series.iloc[2] == 272.5
    assert meta["Fill Value (Data)"] == "-9999.0"
    with pytest.raises(ValueError):
        gldas.parse_timeseries("Error:,token expired\n")


def test_to_daily_units():
    t = pd.date_range("2010-01-01", periods=16, freq="3h")
    acc = pd.Series(0.5, index=t)                 # kg m-2 per 3 h
    rate = pd.Series(1 / 86400, index=t)          # 1 mm/day as kg m-2 s-1
    kelvin = pd.Series(273.15, index=t)
    assert gldas.to_daily(acc, "acc").tolist() == [4.0, 4.0]
    assert gldas.to_daily(rate, "rate").round(6).tolist() == [1.0, 1.0]
    assert gldas.to_daily(kelvin, "kelvin").round(6).tolist() == [0.0, 0.0]
    assert gldas.to_daily(acc.iloc[:7], "acc").isna().all()  # incomplete day


def test_chunks():
    assert gldas._chunks("2000-01-01", "2012-06-30", 5) == [
        ("2000-01-01", "2004-12-31"), ("2005-01-01", "2009-12-31"), ("2010-01-01", "2012-06-30")]


def test_weighted_mean_renormalises_missing_cells():
    w = pd.DataFrame({"gauge_id": ["a", "a"], "cell_lat": [1.0, 2.0], "cell_lon": [0.0, 0.0], "weight": [0.25, 0.75]})
    cells = pd.DataFrame({"cell_lat": [1.0, 2.0, 1.0, 2.0], "cell_lon": 0.0,
                          "date": ["d1", "d1", "d2", "d2"], "x": [4.0, 8.0, 4.0, np.nan]})
    out = weighted_mean(cells, w, ["x"]).set_index("date")["x"]
    assert out["d1"] == pytest.approx(7.0) and out["d2"] == pytest.approx(4.0)


def test_cell_weights(gldas_results):
    w = gldas_results["weights"]
    assert set(w["gauge_id"]) == {"2001", "2004"}
    assert np.allclose(w.groupby("gauge_id")["weight"].sum(), 1.0)
    assert np.allclose((w["cell_lat"] - 0.125) % 0.25, 0) and np.allclose((w["cell_lon"] - 0.125) % 0.25, 0)
    area = w.groupby("gauge_id")["catchment_area_km2"].first()
    assert area["2001"] == pytest.approx(80, rel=1e-3) and area["2004"] == pytest.approx(40, rel=1e-3)


def test_download_caches_and_resumes(gldas_results):
    log, client, w, s = (gldas_results[k] for k in ("log", "client", "weights", "settings"))
    n_cells = len(w[["cell_lat", "cell_lon"]].drop_duplicates())
    assert len(log) == n_cells * len(gldas.VARIABLES) * 3 and (log["error"] == "").all()
    calls = client.calls
    again = gldas.download(w, s.gldas_raw_dir, start="2000-01-01", end="2012-12-31", client=client)
    assert again.empty and client.calls == calls  # everything served from the cache


def test_gldas_pipeline(gldas_results):
    r = gldas_results["results"]
    assert r.meta["source"] == "gldas" and r.gauges == ["2001", "2004"]
    assert r.meta["windows"] == ["2001-2005", "2006-2010"]  # 2011-2012 has 2 years < min_window_years=3
    a = r.annual.set_index(["gauge_id", "hydro_year"])
    assert a["runoff_mm"].between(200, 2000).all()
    assert a["temp_mean"].between(-10, 15).all()
    assert {"snowmelt_total_mm", "evap_total_mm", "snowfall_frac"} <= set(r.annual.columns)
    t = r.trends.set_index(["gauge_id", "metric"])
    assert t.loc[("2004", "com_doy"), "slope_per_decade"] < 0  # synthetic melt moves earlier


def test_obs_vs_gldas(results, gldas_results):
    g = gldas_results["results"]
    annual_cmp = sources.compare_annual(results, g, min_years=5)
    trend_cmp = sources.compare_trends(results, g)
    assert set(annual_cmp["gauge_id"]) == {"2001", "2004"}
    assert annual_cmp.groupby("gauge_id")["first_year"].min().eq(2001).all()  # GLDAS starts in hydro year 2001
    summ = sources.summary(annual_cmp, trend_cmp)
    assert "median_r" in summ
    figs = [
        plots.source_regime(results, g, "2001"),
        plots.source_scatter(annual_cmp, results, "runoff_mm"),
        plots.regime_by_window(g, "2004"),
        plots.hydrograph_vs_history(g, "2004", 2012),
        plots.correlation_matrix(g),
    ]
    if not trend_cmp.empty:
        figs.append(plots.source_trend_scatter(trend_cmp, results, "runoff_mm"))
    assert all(len(f.data) for f in figs)
    assert "GLDAS" in figs[3].layout.yaxis.title.text


def test_save_load_gldas(gldas_results):
    s = gldas_results["settings"]
    loaded = pipeline.load(s.processed_dir)
    assert loaded.meta["source"] == "gldas" and len(loaded.meta["cells"]) == len(gldas_results["weights"])
