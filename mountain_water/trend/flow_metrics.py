"""Annual 'how much water' metrics per catchment and hydrological year."""

from __future__ import annotations

import numpy as np
import pandas as pd

FLOW = "discharge_vol"
SPEC = "discharge_spec"
WINTER_MONTHS = (10, 11, 12, 1, 2, 3)
Q347_QUANTILE = 1 - 347 / 365


def q347_thresholds(daily: pd.DataFrame, flow: str = FLOW) -> pd.Series:
    """Long-term Q347 per gauge: flow reached or exceeded on 347 of 365 days on average."""
    return daily.groupby("gauge_id")[flow].quantile(Q347_QUANTILE)


def annual_volume_metrics(daily: pd.DataFrame, flow: str = FLOW, spec: str = SPEC) -> pd.DataFrame:
    """One row per gauge and hydro year. Volumes are scaled from the mean of available days."""
    df = daily.sort_values(["gauge_id", "date"]).copy()
    df["_min7"] = df.groupby("gauge_id")[flow].transform(lambda s: s.rolling(7, center=True, min_periods=7).mean())
    df["_winter"] = df["date"].dt.month.isin(WINTER_MONTHS)
    df["_q347"] = df["gauge_id"].map(q347_thresholds(df, flow))
    df["_below"] = (df[flow] < df["_q347"]).where(df[flow].notna())

    g = df.groupby(["gauge_id", "hydro_year"])
    out = g.agg(
        mean_flow=(flow, "mean"),
        n_days=("date", "size"),
        q95_low=(flow, lambda s: s.quantile(0.05)),
        q10_high=(flow, lambda s: s.quantile(0.90)),
        peak_flow=(flow, "max"),
        min7_flow=("_min7", "min"),
        days_below_q347=("_below", "sum"),
    )
    if spec in df.columns:
        out["runoff_mm"] = g[spec].mean() * out["n_days"]
    out["volume_hm3"] = out["mean_flow"] * out["n_days"] * 86400 / 1e6
    seasonal = df.groupby(["gauge_id", "hydro_year", "_winter"])[flow].mean().unstack("_winter")
    out["winter_mean_flow"] = seasonal.get(True)
    out["summer_mean_flow"] = seasonal.get(False)
    out["days_below_q347"] = out["days_below_q347"].astype(float)
    return out.drop(columns="n_days").reset_index()


def doy_to_date_label(doy: float, start_month: int = 10, reference_year: int = 2001) -> str:
    """Day of hydrological year -> 'DD Mon' for axis labels (non-leap reference year)."""
    if not np.isfinite(doy):
        return ""
    start = pd.Timestamp(year=reference_year - (1 if start_month != 1 else 0), month=start_month, day=1)
    return (start + pd.Timedelta(days=int(round(doy)) - 1)).strftime("%d %b")
