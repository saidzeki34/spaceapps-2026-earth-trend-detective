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
    """Station x month view over one common period of calendar years (Jan-Dec).

    ``regions``: "ch" = the ``n_gauges`` highest CAMELS-CH river gauges with a complete record over
    the whole period (``country`` / ``water_body_type`` filter; ``None`` disables it); "no" = the NVE
    selection of the last ``build --source nve``. Slopes are relative to the mean over ``baseline`` and
    are only estimated for gauges with >= ``min_complete_years`` complete years, >= ``min_baseline_years``
    of them in the baseline.
    """

    regions: tuple[str, ...] = ("ch", "no")
    raw_dir: Path = Path("data/raw/camels_ch")
    nve_raw_dir: Path = Path("data/raw/nve")
    nve_selection_dir: Path = Path("data/processed/trend_no")  # meta.json of the last `build --source nve`
    processed_dir: Path = Path("data/processed/trend_stations")
    n_gauges: int = 100
    first_year: int = 1981
    last_year: int = 2020
    baseline: tuple[int, int] = (1981, 2000)
    country: str | None = "CH"
    water_body_type: str | None = "stream"
    min_complete_years: int = 30
    min_baseline_years: int = 10
    # Driver comparison: snowpacks below this peak SWE get no snow-free date; slopes need this many paired years.
    min_peak_swe_mm: float = 10.0
    min_paired_years: int = 15
    alpha: float = 0.05

    def __post_init__(self) -> None:
        self.baseline = tuple(int(y) for y in self.baseline)
        self.regions = tuple(self.regions)
        if not self.first_year <= self.baseline[0] <= self.baseline[1] <= self.last_year:
            raise ValueError(f"Baseline {self.baseline} must lie within {self.first_year}-{self.last_year}")
        if not set(self.regions) <= {"ch", "no"} or not self.regions:
            raise ValueError(f"regions must be 'ch' and/or 'no', got {self.regions}")
