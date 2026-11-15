"""Within-year flow variability, kept separate from long-term change."""

from __future__ import annotations

import pandas as pd

FLOW = "discharge_vol"


def annual_variability_metrics(daily: pd.DataFrame, flow: str = FLOW) -> pd.DataFrame:
    df = daily.sort_values(["gauge_id", "date"]).copy()
    df["_abs_change"] = df.groupby("gauge_id")[flow].diff().abs()
    g = df.groupby(["gauge_id", "hydro_year"])
    out = pd.DataFrame({
        "cv_daily": g[flow].std() / g[flow].mean(),
        "flashiness": g["_abs_change"].sum(min_count=1) / g[flow].sum(min_count=1),
    })
    return out.reset_index()


def interannual_cv(annual: pd.DataFrame, metric: str, window_col: str = "window") -> pd.DataFrame:
    """Year-to-year coefficient of variation of an annual metric per gauge and comparison window."""
    g = annual.groupby(["gauge_id", window_col])[metric]
    return (g.std() / g.mean()).rename(f"{metric}_interannual_cv").reset_index()
