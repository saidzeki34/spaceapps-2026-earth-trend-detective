"""Prepare observed series for analysis: hydrological years, gap handling, completeness, catchment filter."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .settings import CatchmentFilter

log = logging.getLogger(__name__)

FLOW = "discharge_vol"


def add_hydro_year(df: pd.DataFrame, start_month: int = 10) -> pd.DataFrame:
    """Add ``hydro_year`` (labelled by end year) and ``hydro_doy`` (1 = first day of the hydro year)."""
    out = df.copy()
    date = out["date"]
    year = date.dt.year + (date.dt.month >= start_month).astype(int) if start_month != 1 else date.dt.year
    out["hydro_year"] = year.astype(int)
    start = pd.to_datetime(dict(year=out["hydro_year"] - (1 if start_month != 1 else 0), month=start_month, day=1))
    out["hydro_doy"] = (date - start).dt.days + 1
    return out


def fill_short_gaps(df: pd.DataFrame, columns: list[str], max_gap: int) -> pd.DataFrame:
    """Linearly interpolate interior gaps of at most ``max_gap`` days per gauge; longer gaps stay NaN.

    Adds ``<col>_filled`` flags so filled values remain distinguishable from observations.
    """
    out = df.sort_values(["gauge_id", "date"]).copy()
    for col in columns:
        if col not in out.columns:
            continue

        def _fill(s: pd.Series) -> pd.Series:
            isna = s.isna()
            run_id = (~isna).cumsum()
            run_len = isna.groupby(run_id).transform("sum")
            interp = s.interpolate(limit_area="inside")
            return s.where(~(isna & (run_len <= max_gap)), interp)

        filled = out.groupby("gauge_id", group_keys=False)[col].apply(_fill)
        out[f"{col}_filled"] = out[col].isna() & filled.notna()
        out[col] = filled
    return out


def year_completeness(df: pd.DataFrame, column: str = FLOW) -> pd.DataFrame:
    """Share of valid days per gauge and hydrological year (before gap filling, if ``_filled`` exists)."""
    valid = df[column].notna()
    if f"{column}_filled" in df.columns:
        valid &= ~df[f"{column}_filled"]
    g = df.assign(_valid=valid).groupby(["gauge_id", "hydro_year"])
    out = g.agg(n_days=("date", "size"), n_valid=("_valid", "sum")).reset_index()
    # Expected length of the hydrological year, so a truncated first/last year counts as incomplete.
    # The hydro year contains February of its label year (start month Jan or after Feb).
    out["expected_days"] = out["hydro_year"].map(lambda y: 366 if pd.Timestamp(year=y, month=1, day=1).is_leap_year else 365)
    out["completeness"] = out["n_valid"] / out["expected_days"]
    return out


def valid_years(completeness: pd.DataFrame, threshold: float) -> pd.DataFrame:
    return completeness.loc[completeness["completeness"] >= threshold, ["gauge_id", "hydro_year"]]


def _first_column(attrs: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in attrs.columns:
            return c
    return None


def select_catchments(
    attrs: pd.DataFrame, completeness: pd.DataFrame, flt: CatchmentFilter, year_threshold: float
) -> tuple[list[str], pd.DataFrame]:
    """Apply the mountain-headwater filter. Returns (gauge_ids, step log)."""
    keep = attrs[["gauge_id"]].copy()
    keep["keep"] = True
    steps = [("all catchments", int(keep["keep"].sum()))]

    def apply(label: str, candidates: tuple[str, ...], limit, op) -> None:
        if limit is None:
            return
        col = _first_column(attrs, candidates)
        if col is None:
            log.warning("Filter '%s' skipped: none of %s in attributes", label, candidates)
            steps.append((f"{label}: SKIPPED (no column)", int(keep["keep"].sum())))
            return
        values = pd.to_numeric(attrs[col], errors="coerce")
        keep["keep"] &= op(values, limit).fillna(False).to_numpy()
        steps.append((f"{label} [{col}]", int(keep["keep"].sum())))

    apply(f"mean elevation >= {flt.min_mean_elevation_m} m", flt.elevation_columns, flt.min_mean_elevation_m,
          lambda v, x: v >= x)
    apply(f"area <= {flt.max_area_km2} km2", flt.area_columns, flt.max_area_km2, lambda v, x: v <= x)
    apply(f"reservoirs <= {flt.max_reservoirs}", flt.reservoir_columns, flt.max_reservoirs, lambda v, x: v <= x)

    n_valid = valid_years(completeness, year_threshold).groupby("gauge_id").size()
    keep["keep"] &= keep["gauge_id"].map(n_valid).fillna(0).to_numpy() >= flt.min_valid_years
    steps.append((f">= {flt.min_valid_years} years with >= {year_threshold:.0%} valid flow", int(keep["keep"].sum())))

    return keep.loc[keep["keep"], "gauge_id"].tolist(), pd.DataFrame(steps, columns=["step", "remaining"])


def windows(years: list[int] | np.ndarray, size: int = 10, min_size: int = 8) -> list[tuple[int, int]]:
    """Consecutive (start, end) year blocks of ``size`` years; a short final block is kept if >= ``min_size``."""
    years = sorted(set(int(y) for y in years))
    if not years:
        return []
    out = []
    start = years[0]
    while start <= years[-1]:
        end = min(start + size - 1, years[-1])
        if end - start + 1 >= min_size:
            out.append((start, end))
        start += size
    return out


def window_label(window: tuple[int, int]) -> str:
    return f"{window[0]}-{window[1]}"


def assign_window(years: pd.Series, wins: list[tuple[int, int]]) -> pd.Series:
    labels = pd.Series(pd.NA, index=years.index, dtype="object")
    for w in wins:
        labels[(years >= w[0]) & (years <= w[1])] = window_label(w)
    return labels
