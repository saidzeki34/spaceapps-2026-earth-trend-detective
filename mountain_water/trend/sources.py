"""Compare two sources for the same catchments: CAMELS-CH observations vs GLDAS-2.1 model output.

Only hydrological years present in both are used. GLDAS runoff is unrouted model runoff on a
0.25° grid, so differences in timing and in small catchments are expected; this comparison shows
how far GLDAS can stand in for observations, not which one is "right".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import trends
from .registry import info

DEFAULT_METRICS = [
    "runoff_mm", "summer_mean_flow", "winter_mean_flow", "q95_low", "com_doy", "half_volume_doy",
    "precip_total_mm", "temp_mean", "swe_max_mm", "snowfall_frac",
]


def common_annual(obs, model, metrics: list[str]) -> pd.DataFrame:
    keys = ["gauge_id", "hydro_year"]
    a = obs.annual[keys + [m for m in metrics if m in obs.annual]]
    b = model.annual[keys + [m for m in metrics if m in model.annual]]
    return a.merge(b, on=keys, suffixes=("_obs", "_model"))


def compare_annual(obs, model, metrics: list[str] | None = None, min_years: int = 10) -> pd.DataFrame:
    """Per catchment and metric over common years: means, bias and year-to-year correlation."""
    metrics = metrics or DEFAULT_METRICS
    d = common_annual(obs, model, metrics)
    rows = []
    for gauge_id, grp in d.groupby("gauge_id"):
        for m in metrics:
            if f"{m}_obs" not in grp or f"{m}_model" not in grp:
                continue
            pair = grp[[f"{m}_obs", f"{m}_model"]].dropna()
            if len(pair) < min_years:
                continue
            x, y = pair.iloc[:, 0].to_numpy(dtype=float), pair.iloc[:, 1].to_numpy(dtype=float)
            bias = y.mean() - x.mean()
            r = np.corrcoef(x, y)[0, 1] if np.ptp(x) > 0 and np.ptp(y) > 0 else np.nan
            rows.append(dict(
                gauge_id=gauge_id, metric=m, n_years=len(pair),
                first_year=int(grp.loc[pair.index, "hydro_year"].min()),
                last_year=int(grp.loc[pair.index, "hydro_year"].max()),
                mean_obs=x.mean(), mean_model=y.mean(), bias=bias,
                bias_pct=bias / x.mean() * 100 if info(m).relative and x.mean() else np.nan,
                r=r,
            ))
    return pd.DataFrame(rows)


def compare_trends(obs, model, metrics: list[str] | None = None, alpha: float = 0.05) -> pd.DataFrame:
    """Sen's slope per decade from both sources, recomputed on the common years only."""
    metrics = metrics or DEFAULT_METRICS
    d = common_annual(obs, model, metrics)
    out = []
    for suffix in ("obs", "model"):
        cols = {f"{m}_{suffix}": m for m in metrics if f"{m}_{suffix}" in d}
        t = trends.trend_table(d.rename(columns=cols)[["gauge_id", "hydro_year", *cols.values()]],
                               list(cols.values()), alpha, min_years=10)
        if t.empty:
            continue
        keep = ["gauge_id", "metric", "slope_per_decade", "pct_per_decade", "p", "significant"]
        out.append(t[keep].rename(columns={c: f"{c}_{suffix}" for c in keep[2:]}))
    if len(out) < 2:
        return pd.DataFrame()
    both = out[0].merge(out[1], on=["gauge_id", "metric"])
    both["same_direction"] = np.sign(both["slope_per_decade_obs"]) == np.sign(both["slope_per_decade_model"])
    return both


def summary(annual_cmp: pd.DataFrame, trend_cmp: pd.DataFrame) -> pd.DataFrame:
    """Across catchments: median bias, median correlation and share of trends with the same sign."""
    a = annual_cmp.groupby("metric").agg(
        n_catchments=("gauge_id", "size"), median_bias=("bias", "median"),
        median_bias_pct=("bias_pct", "median"), median_r=("r", "median"),
    )
    if not trend_cmp.empty:
        a = a.join(trend_cmp.groupby("metric")["same_direction"].mean().rename("share_same_trend_direction"))
    return a.reset_index()


def regime_pair(obs, model, gauge_id: str, smooth_days: int = 15) -> pd.DataFrame:
    """Mean seasonal hydrograph (m³/s) of both sources over their common years."""
    years = set(obs.annual.loc[obs.annual["gauge_id"] == gauge_id, "hydro_year"]) & \
        set(model.annual.loc[model.annual["gauge_id"] == gauge_id, "hydro_year"])
    frames = []
    for name, res in (("observed", obs), ("gldas", model)):
        d = res.daily[(res.daily["gauge_id"] == gauge_id) & res.daily["hydro_year"].isin(years)
                      & (res.daily["hydro_doy"] <= 365)]
        reg = d.groupby("hydro_doy")["discharge_vol"].mean()
        if smooth_days > 1:
            reg = reg.rolling(smooth_days, center=True, min_periods=1).mean()
        frames.append(reg.rename(name))
    out = pd.concat(frames, axis=1).reset_index()
    out.attrs["years"] = (min(years), max(years)) if years else None
    return out
