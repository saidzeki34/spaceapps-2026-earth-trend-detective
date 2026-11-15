"""Long-term change: Mann-Kendall significance and Sen's slope per catchment and metric.

Annual series are often autocorrelated, which inflates significance in the classic test, so
trend-free pre-whitening is applied first. Many catchments are tested at once, so p-values are also
adjusted with Benjamini-Hochberg (false discovery rate) per metric.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pymannkendall as mk

from .registry import info


def sen_slope(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Sen's slope (per year) and intercept using actual years, so missing years are handled."""
    ok = np.isfinite(values) & np.isfinite(years)
    x, y = years[ok], values[ok]
    if len(x) < 3:
        return np.nan, np.nan
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    slopes = (y[j] - y[i])[dx != 0] / dx[dx != 0]
    slope = float(np.median(slopes))
    return slope, float(np.median(y - slope * x))


def mann_kendall_p(values: np.ndarray) -> float:
    """Two-sided Mann-Kendall p-value with trend-free pre-whitening (Yue et al. 2002).

    Falls back to the classic test if pre-whitening is undefined (e.g. constant residuals).
    """
    v = values[np.isfinite(values)]
    if len(v) < 8 or np.ptp(v) == 0:
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            p = float(mk.trend_free_pre_whitening_modification_test(v).p)
        except (ZeroDivisionError, ValueError, FloatingPointError):
            p = np.nan
        if not np.isfinite(p):
            p = float(mk.original_test(v).p)
    return p


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=p.index)
    ok = p.dropna()
    if ok.empty:
        return out
    order = ok.sort_values()
    m = len(order)
    adj = order.to_numpy() * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1].clip(max=1.0)
    out[order.index] = adj
    return out


def trend_table(annual: pd.DataFrame, metrics: list[str], alpha: float = 0.05, min_years: int = 15) -> pd.DataFrame:
    """One row per gauge and metric with slope per decade (absolute and % of mean), p and FDR-adjusted p."""
    rows = []
    for gauge_id, grp in annual.groupby("gauge_id"):
        grp = grp.sort_values("hydro_year")
        years = grp["hydro_year"].to_numpy(dtype=float)
        for metric in metrics:
            if metric not in grp:
                continue
            values = grp[metric].to_numpy(dtype=float)
            n = int(np.isfinite(values).sum())
            if n < min_years:
                continue
            slope, intercept = sen_slope(years, values)
            mean = float(np.nanmean(values))
            rows.append(dict(
                gauge_id=gauge_id, metric=metric, kind=info(metric).kind, n_years=n,
                first_year=int(years[np.isfinite(values)].min()), last_year=int(years[np.isfinite(values)].max()),
                mean=mean, slope_per_decade=slope * 10, intercept=intercept,
                pct_per_decade=(slope * 10 / mean * 100) if info(metric).relative and mean else np.nan,
                p=mann_kendall_p(values),
            ))
    out = pd.DataFrame(rows, columns=[
        "gauge_id", "metric", "kind", "n_years", "first_year", "last_year", "mean", "slope_per_decade",
        "intercept", "pct_per_decade", "p"])
    if out.empty:
        return out.assign(p_fdr=np.nan, significant=False, significant_fdr=False, direction="")
    out["p_fdr"] = out.groupby("metric", group_keys=False)["p"].apply(benjamini_hochberg)
    out["significant"] = out["p"] < alpha
    out["significant_fdr"] = out["p_fdr"] < alpha
    out["direction"] = np.sign(out["slope_per_decade"]).map({1.0: "increase", -1.0: "decrease", 0.0: "none"})
    return out
