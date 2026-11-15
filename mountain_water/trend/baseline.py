"""Historical reference: day-of-year flow percentiles, to place a given year in its history."""

from __future__ import annotations

import pandas as pd

FLOW = "discharge_vol"
DEFAULT_QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def daily_climatology(
    daily: pd.DataFrame,
    gauge_id: str,
    years: tuple[int, int] | None = None,
    column: str = FLOW,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
    smooth_days: int = 7,
) -> pd.DataFrame:
    """Percentiles of ``column`` per day of hydrological year, over the reference ``years`` (inclusive).

    Day 366 only exists in leap years and is dropped. Percentiles are smoothed with a centred
    rolling mean so the band is readable; set ``smooth_days=1`` to disable.
    """
    d = daily[(daily["gauge_id"] == gauge_id) & (daily["hydro_doy"] <= 365)]
    if years:
        d = d[d["hydro_year"].between(*years)]
    clim = d.groupby("hydro_doy")[column].quantile(list(quantiles)).unstack()
    clim.columns = [f"q{int(round(q * 100)):02d}" for q in quantiles]
    clim["mean"] = d.groupby("hydro_doy")[column].mean()
    if smooth_days > 1:
        clim = clim.rolling(smooth_days, center=True, min_periods=1).mean()
    return clim.reset_index()


def year_vs_climatology(
    daily: pd.DataFrame,
    gauge_id: str,
    year: int,
    reference: tuple[int, int] | None = None,
    column: str = FLOW,
) -> pd.DataFrame:
    """Daily values of one hydrological year joined to the reference percentiles, with a percentile rank."""
    clim = daily_climatology(daily, gauge_id, reference, column)
    ref = daily[(daily["gauge_id"] == gauge_id)]
    if reference:
        ref = ref[ref["hydro_year"].between(*reference)]
    this = daily[(daily["gauge_id"] == gauge_id) & (daily["hydro_year"] == year)][["date", "hydro_doy", column]]
    out = this.merge(clim, on="hydro_doy", how="left")
    by_doy = {doy: grp[column].dropna().to_numpy() for doy, grp in ref.groupby("hydro_doy")}
    out["percentile_rank"] = [
        (by_doy[doy] < v).mean() * 100 if doy in by_doy and len(by_doy[doy]) and pd.notna(v) else float("nan")
        for doy, v in zip(out["hydro_doy"], out[column])
    ]
    return out
