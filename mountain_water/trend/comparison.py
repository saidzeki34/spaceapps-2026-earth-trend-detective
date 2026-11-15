"""Compare 10-year windows with each other, and catchment trends with catchment properties."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .registry import info


def window_comparison(annual: pd.DataFrame, metrics: list[str], window_col: str = "window") -> pd.DataFrame:
    """Per gauge, metric and window: mean, change vs the first (reference) window and vs the previous window.

    Changes are absolute, plus in % where a ratio is meaningful (see ``MetricInfo.relative``).
    ``p_vs_reference`` is a Mann-Whitney U test of the window's annual values against the reference
    window's (two-sided). With ~10 values per window it only detects large shifts.
    """
    rows = []
    for gauge_id, grp in annual.dropna(subset=[window_col]).groupby("gauge_id"):
        wins = sorted(grp[window_col].unique())
        for metric in metrics:
            if metric not in grp:
                continue
            values = {w: grp.loc[grp[window_col] == w, metric].dropna().to_numpy(dtype=float) for w in wins}
            ref = values[wins[0]]
            prev = None
            for w in wins:
                v = values[w]
                mean = float(v.mean()) if len(v) else np.nan
                ref_mean = float(ref.mean()) if len(ref) else np.nan
                p = np.nan
                if w != wins[0] and len(v) >= 5 and len(ref) >= 5:
                    p = float(stats.mannwhitneyu(v, ref, alternative="two-sided").pvalue)
                pct_ok = info(metric).relative
                rows.append(dict(
                    gauge_id=gauge_id, metric=metric, window=w, n_years=len(v), mean=mean,
                    std=float(v.std(ddof=1)) if len(v) > 1 else np.nan,
                    change_vs_reference=mean - ref_mean,
                    pct_vs_reference=(mean - ref_mean) / ref_mean * 100 if pct_ok and ref_mean else np.nan,
                    change_vs_previous=mean - prev if prev is not None else np.nan,
                    pct_vs_previous=(mean - prev) / prev * 100 if pct_ok and prev else np.nan,
                    p_vs_reference=p,
                ))
                prev = mean
    return pd.DataFrame(rows)


def trend_vs_attribute(trends: pd.DataFrame, attrs: pd.DataFrame, metric: str, attribute: str,
                       value: str | None = None) -> dict:
    """Across catchments: does the trend of ``metric`` relate to a static ``attribute`` (e.g. elevation)?

    Uses % per decade for amounts and units per decade (days, °C) otherwise, unless ``value`` is given.
    """
    value = value or ("pct_per_decade" if info(metric).relative else "slope_per_decade")
    t = trends[trends["metric"] == metric][["gauge_id", value]]
    d = t.merge(attrs[["gauge_id", attribute]], on="gauge_id").dropna()
    d[attribute] = pd.to_numeric(d[attribute], errors="coerce")
    d = d.dropna()
    if len(d) < 5:
        return dict(metric=metric, attribute=attribute, n=len(d), r=np.nan, p=np.nan)
    r, p = stats.spearmanr(d[attribute], d[value])
    return dict(metric=metric, attribute=attribute, n=len(d), r=float(r), p=float(p))


def trend_attribute_matrix(trends: pd.DataFrame, attrs: pd.DataFrame, metrics: list[str],
                           attributes: list[str]) -> pd.DataFrame:
    rows = [trend_vs_attribute(trends, attrs, m, a) for m in metrics for a in attributes if a in attrs]
    return pd.DataFrame(rows)
