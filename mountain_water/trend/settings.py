"""Tunable settings for the trend pipeline. Defaults are starting points for team review."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CatchmentFilter:
    """'Mountain catchment near the source' selection. ``None`` disables a criterion.

    Each entry in ``*_columns`` lists candidate attribute names; the first one present
    in the dataset is used, otherwise the criterion is skipped with a warning.
    """

    min_mean_elevation_m: float | None = 1500.0
    max_area_km2: float | None = 500.0
    max_reservoirs: int | None = 0
    min_valid_years: int = 30

    elevation_columns: tuple[str, ...] = ("elev_mean", "mean_elev", "elevation_mean")
    area_columns: tuple[str, ...] = ("area", "area_km2", "catchment_area")
    reservoir_columns: tuple[str, ...] = ("num_reservoir", "res_num", "reservoir_num", "n_reservoirs")


@dataclass
class TrendSettings:
    raw_dir: Path = Path("data/raw/camels_ch")
    processed_dir: Path = Path("data/processed/trend")

    # Hydrological year starts in October (snow accumulation -> melt in one year).
    # Years are labelled by the calendar year in which they end (Oct 2019-Sep 2020 = 2020).
    hydro_year_start_month: int = 10
    min_year_completeness: float = 0.9
    max_gap_fill_days: int = 5

    # Comparison windows: consecutive blocks of ``window_years`` starting at the first full year.
    window_years: int = 10
    min_window_years: int = 8

    alpha: float = 0.05
    filters: CatchmentFilter = field(default_factory=CatchmentFilter)
