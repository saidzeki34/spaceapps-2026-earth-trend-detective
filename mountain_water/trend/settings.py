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

    min_mean_elevation_m: float | None = 1500.0  # Norway: median elevation (see TrendSettings.nve)
    max_area_km2: float | None = 500.0
    max_reservoirs: int | None = 0
    min_valid_years: int = 30
    elevation_label: str = "mean elevation"  # how the elevation criterion is shown in the selection log

    elevation_columns: tuple[str, ...] = ("elev_mean", "mean_elev", "elevation_mean")
    area_columns: tuple[str, ...] = ("area", "area_km2", "catchment_area")
    reservoir_columns: tuple[str, ...] = ("num_reservoir", "res_num", "reservoir_num", "n_reservoirs")


@dataclass
class TrendSettings:
    region: str = "ch"  # "ch" (CAMELS-CH) or "no" (NVE); GLDAS runs on either region's catchments
    raw_dir: Path = Path("data/raw/camels_ch")
    processed_dir: Path = Path("data/processed/trend")
    gldas_raw_dir: Path = Path("data/raw/gldas")
    nve_raw_dir: Path = Path("data/raw/nve")

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

    @classmethod
    def gldas(cls, region: str = "ch", **overrides) -> "TrendSettings":
        """Defaults for GLDAS-2.1 (record starts 2000): >= 20 valid years, keep a final window of >= 5 years."""
        processed = "data/processed/trend_gldas" if region == "ch" else f"data/processed/trend_{region}_gldas"
        s = cls(region=region, processed_dir=Path(processed), min_window_years=5,
                filters=CatchmentFilter(min_valid_years=20))
        for key, value in overrides.items():
            setattr(s, key, value)
        return s

    @classmethod
    def nve(cls, **overrides) -> "TrendSettings":
        """Norway (NVE): median catchment elevation >= 800 m, <= 500 km², unregulated, >= 30 valid years.

        The record starts in October 1960 (hydrological years 1961-latest), so the last 10-year
        window is kept when it has >= 5 years.
        """
        s = cls(region="no", processed_dir=Path("data/processed/trend_no"), min_window_years=5,
                filters=CatchmentFilter(
                    min_mean_elevation_m=800.0, max_area_km2=500.0, max_reservoirs=0, min_valid_years=30,
                    elevation_columns=("elevation",), area_columns=("area",), reservoir_columns=("regulated",),
                    elevation_label="median elevation",
                ))
        for key, value in overrides.items():
            setattr(s, key, value)
        return s

    @classmethod
    def observed(cls, region: str) -> "TrendSettings":
        return cls.nve() if region == "no" else cls()

@dataclass
class StationNetworkSettings:
    """Station x month view: the highest river gauges with a complete daily record over one common period.

    Calendar years (Jan-Dec), so the month columns run January to December. Slopes are expressed
    relative to the mean over ``baseline``. ``None`` disables the country / water body filter.
    """

    raw_dir: Path = Path("data/raw/camels_ch")
    processed_dir: Path = Path("data/processed/trend_stations")
    n_gauges: int = 100
    first_year: int = 1981
    last_year: int = 2020
    baseline: tuple[int, int] = (1981, 2000)
    country: str | None = "CH"
    water_body_type: str | None = "stream"
    alpha: float = 0.05

    def __post_init__(self) -> None:
        self.baseline = tuple(int(y) for y in self.baseline)
        if not self.first_year <= self.baseline[0] <= self.baseline[1] <= self.last_year:
            raise ValueError(f"Baseline {self.baseline} must lie within {self.first_year}-{self.last_year}")
