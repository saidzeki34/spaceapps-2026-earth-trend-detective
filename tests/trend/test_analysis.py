import numpy as np
import pandas as pd
import pytest

from mountain_water.trend import pipeline, plots, trends
from mountain_water.trend.timing import _timing_one_year


def test_sen_slope_uses_real_years_with_gaps():
    years = np.array([2000, 2001, 2003, 2006, 2010], dtype=float)
    slope, intercept = trends.sen_slope(years, 2 * years + 1)
    assert slope == pytest.approx(2) and intercept == pytest.approx(1)


def test_benjamini_hochberg():
    p = pd.Series([0.01, 0.04, 0.03, np.nan])
    adj = trends.benjamini_hochberg(p)
    assert adj.iloc[:3].round(4).tolist() == [0.03, 0.04, 0.04]
    assert np.isnan(adj.iloc[3])


def test_timing_metrics_on_symmetric_peak():
    doy = np.arange(1, 366)
    q = 1 + 10 * np.exp(-0.5 * ((doy - 183) / 20) ** 2)
    t = _timing_one_year(doy, q)
    assert t["peak_doy"] == 183
    assert t["half_volume_doy"] == pytest.approx(183, abs=1)
    assert t["com_doy"] == pytest.approx(183, abs=1)
    assert t["onset_doy"] < 183
    q[10] = np.nan
    assert np.isnan(_timing_one_year(doy, q)["com_doy"])


def test_pipeline_selection_and_windows(results):
    assert results.gauges == ["2001", "2002", "2003", "2004"]  # low, regulated and gappy gauges removed
    assert results.meta["windows"] == ["1982-1991", "1992-2001", "2002-2011", "2012-2020"]
    assert not results.annual["window"].isna().any()


def test_pipeline_detects_earlier_flow(results):
    t = results.trends.set_index(["gauge_id", "metric"])
    assert t.loc[("2004", "com_doy"), "slope_per_decade"] < -3
    assert t.loc[("2004", "com_doy"), "significant_fdr"]
    assert not t.loc[("2003", "com_doy"), "significant_fdr"]  # synthetic gauge without timing shift
    assert t.loc[("2001", "temp_mean"), "slope_per_decade"] > 0
    assert np.isnan(t.loc[("2001", "temp_mean"), "pct_per_decade"])  # no % for temperatures


def test_window_comparison_reference_row(results):
    w = results.window_comparison
    first = w[(w["gauge_id"] == "2001") & (w["metric"] == "mean_flow") & (w["window"] == "1982-1991")].iloc[0]
    assert first["change_vs_reference"] == 0 and np.isnan(first["p_vs_reference"])


def test_attribution_sums_to_observed(results):
    a = results.attribution
    total = a["from_precip_per_decade"] + a["from_temp_per_decade"] + a["residual_per_decade"]
    assert np.allclose(total, a["observed_change_per_decade"])


def test_save_load_roundtrip(results, settings):
    loaded = pipeline.load(settings.processed_dir)
    assert loaded.gauges == results.gauges
    assert loaded.gauge_label("2001") == "Testbach 2001 (2001)"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_all_figures_build(results, theme):
    g = "2001"
    figs = [
        plots.hydrograph_vs_history(results, g, 2020, theme=theme),
        plots.regime_by_window(results, g, theme=theme),
        plots.regime_by_window(results, g, normalized=True, theme=theme),
        plots.annual_metric(results, g, "com_doy", theme=theme),
        plots.annual_metric(results, g, "mean_flow", theme=theme),
        plots.daily_heatmap(results, g, theme=theme),
        plots.window_means(results, g, "summer_mean_flow", theme=theme),
        plots.correlation_matrix(results, theme=theme),
        plots.correlation_matrix(results, g, theme=theme),
        plots.driver_scatter(results, g, "summer_mean_flow", "temp_summer", theme=theme),
        plots.trend_heatmap(results, "volume", theme=theme),
        plots.trend_heatmap(results, "timing", theme=theme),
        plots.window_change_heatmap(results, "com_doy", theme=theme),
        plots.trend_map(results, "mean_flow", theme=theme),
        plots.trend_vs_attribute(results, "com_doy", "elevation", theme=theme),
        plots.attribution_bars(results, theme=theme),
        plots.selection_summary(results, theme=theme),
    ]
    assert all(len(f.data) > 0 for f in figs)
    assert plots.monthly_regime_table(results, g).shape == (12, 4)
