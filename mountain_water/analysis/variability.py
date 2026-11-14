"""Three distinct axes; no composite score."""
import numpy as np

from mountain_water.analysis.trends import estimate_trend


def calculate_variability(periods, baseline_mean_volume: float | None) -> dict:
    quantity = estimate_trend(periods.year, periods.season_volume_m3, "m3/year")
    timing = estimate_trend(periods.year, periods.half_volume_day, "days/year")
    result = {"quantity_trend": quantity, "timing_trend": timing,
              "baseline_mean_volume_m3": baseline_mean_volume,
              "quantity_pct_decade": None, "timing_days_decade": None,
              "quantity_interval_pct_decade": None, "timing_interval_days_decade": None,
              "normalisation_uncertainty": "Reference mean held fixed; its estimation uncertainty is not propagated.",
              "residual_sd_m3": None, "variability_pct": None,
              "status": "insufficient_evidence"}
    if timing["slope_per_year"] is not None:
        result["timing_days_decade"] = 10 * timing["slope_per_year"]
    if timing["interval"] is not None:
        result["timing_interval_days_decade"] = [10 * v for v in timing["interval"]]
    if baseline_mean_volume is None or not np.isfinite(baseline_mean_volume) or baseline_mean_volume <= 0:
        result["status"] = "invalid_normalisation"
        return result
    t = periods.dropna(subset=["season_volume_m3"])
    slope = quantity["slope_per_year"]
    if slope is None or len(t) < 3:
        return result
    predicted = t.season_volume_m3.mean() + slope * (t.year - t.year.mean())
    residual = t.season_volume_m3 - predicted
    sd = float(np.std(residual, ddof=1))
    result.update(quantity_pct_decade=1000 * slope / baseline_mean_volume,
                  residual_sd_m3=sd, variability_pct=100 * sd / baseline_mean_volume,
                  status="descriptive")
    if quantity["interval"] is not None:
        result["quantity_interval_pct_decade"] = [1000 * v / baseline_mean_volume for v in quantity["interval"]]
    return result
