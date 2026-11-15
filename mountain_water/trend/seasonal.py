"""Seasonal flow regime per comparison window: shows shifts in *when* water is available."""

from __future__ import annotations

import pandas as pd

FLOW = "discharge_vol"


def hydro_month_order(start_month: int = 10) -> list[int]:
    return [(start_month - 1 + i) % 12 + 1 for i in range(12)]


def monthly_regime(daily: pd.DataFrame, column: str = FLOW, window_col: str = "window") -> pd.DataFrame:
    """Mean monthly value per gauge and window plus the Pardé coefficient (month mean / annual mean)."""
    d = daily.dropna(subset=[window_col]).assign(month=daily["date"].dt.month)
    reg = d.groupby(["gauge_id", window_col, "month"])[column].mean().rename("mean").reset_index()
    annual = d.groupby(["gauge_id", window_col])[column].mean().rename("annual_mean")
    reg = reg.join(annual, on=["gauge_id", window_col])
    reg["parde"] = reg["mean"] / reg["annual_mean"]
    return reg.drop(columns="annual_mean")


def daily_regime(
    daily: pd.DataFrame, column: str = FLOW, window_col: str = "window", smooth_days: int = 15
) -> pd.DataFrame:
    """Mean value per day of hydrological year for each gauge and window (smoothed)."""
    d = daily[daily["hydro_doy"] <= 365].dropna(subset=[window_col])
    reg = d.groupby(["gauge_id", window_col, "hydro_doy"])[column].mean().rename("mean").reset_index()
    if smooth_days > 1:
        reg["mean"] = reg.groupby(["gauge_id", window_col])["mean"].transform(
            lambda s: s.rolling(smooth_days, center=True, min_periods=1).mean()
        )
    return reg
