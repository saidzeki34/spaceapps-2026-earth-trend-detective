"""Shared records. All intervals are half-open [start, end), stored in UTC."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Generic, TypeVar

import numpy as np
import pandas as pd


class Status(StrEnum):
    READY = "ready"
    AUTHENTICATION_REQUIRED = "authentication_required"
    PENDING = "pending"
    UNSUPPORTED = "unsupported"
    NO_DATA = "no_data"
    ERROR = "error"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_url: str
    identifier: str
    version: str
    retrieved_at: str
    license: str
    attribution: str
    units: str
    kind: str = "observed"
    transformations: tuple[str, ...] = ()

    def __post_init__(self):
        if not all((self.provider, self.source_url, self.identifier, self.version,
                    self.retrieved_at, self.license, self.attribution, self.units)):
            raise ValueError("Provenance fields must be populated; use 'unknown' explicitly where needed.")
        if self.kind not in {"observed", "modelled", "forecast", "synthetic", "satellite_retrieval"}:
            raise ValueError("Unknown provenance kind.")
        stamp = pd.Timestamp(self.retrieved_at)
        if stamp.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone.")


@dataclass(frozen=True)
class Outlet:
    id: str
    name: str
    country: str
    provider: str
    station_id: str
    latitude: float | None
    longitude: float | None
    catchment_id: str
    catchment_area_km2: float | None
    catchment_source: str
    source_url: str
    supported_start: str
    supported_end: str
    regulation_status: str
    geometry: dict | None = None
    calendar_timezone: str = "UTC"
    notes: str = ""

    def __post_init__(self):
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ValueError("Invalid outlet latitude.")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ValueError("Invalid outlet longitude.")
        if self.catchment_area_km2 is not None and self.catchment_area_km2 <= 0:
            raise ValueError("Catchment area must be positive.")
        if self.geometry and self.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Catchment geometry must be a WGS84 Polygon or MultiPolygon.")


def validate_intervals(table: pd.DataFrame, value_column: str) -> pd.DataFrame:
    required = {"start", "end", value_column}
    if not required.issubset(table):
        raise ValueError(f"Table needs columns: {', '.join(sorted(required))}.")
    t = table.copy().reset_index(drop=True)
    for col in ("start", "end"):
        # Never guess the timezone of an imported timestamp.
        if any(pd.Timestamp(v).tzinfo is None for v in t[col]):
            raise ValueError("Interval timestamps must include a UTC offset.")
        t[col] = pd.to_datetime(t[col], utc=True, errors="raise")
        if t[col].isna().any():
            raise ValueError("Missing interval boundaries are not allowed.")
    if not t.start.is_monotonic_increasing or t.start.duplicated().any():
        raise ValueError("Intervals must be sorted and have unique starts.")
    if (t.end <= t.start).any() or (t.start.iloc[1:].reset_index(drop=True)
                                  < t.end.iloc[:-1].reset_index(drop=True)).any():
        raise ValueError("Intervals must have positive duration and may not overlap.")
    t[value_column] = pd.to_numeric(t[value_column], errors="raise").astype(float)
    if np.isinf(t[value_column]).any():
        raise ValueError("Infinite values are not valid observations.")
    return t


@dataclass
class FlowSeries:
    outlet: Outlet
    table: pd.DataFrame
    provenance: Provenance
    meaning: str = "interval_average"
    origin: str = "fresh"

    def __post_init__(self):
        self.table = validate_intervals(self.table, "discharge_m3s")
        if self.meaning != "interval_average":
            raise ValueError("Instantaneous samples need explicit integration and a gap rule first.")
        if self.provenance.units != "m3/s":
            raise ValueError("FlowSeries requires discharge in m3/s.")
        if (self.table.discharge_m3s.dropna() < 0).any():
            raise ValueError("Negative outlet discharge is unsupported; preserve it as invalid/missing.")
        if "quality" not in self.table or "valid" not in self.table:
            raise ValueError("FlowSeries requires retained quality flags and explicit valid booleans.")
        if not self.table.valid.map(lambda v: isinstance(v, (bool, np.bool_))).all():
            raise ValueError("valid must contain booleans, not strings or missing values.")
        self.table["valid"] = self.table.valid & self.table.discharge_m3s.notna()


@dataclass
class DriverSeries:
    outlet_id: str
    variable: str
    table: pd.DataFrame
    provenance: Provenance
    spatial_resolution_m: float
    aggregation: str
    origin: str = "fresh"

    def __post_init__(self):
        self.table = validate_intervals(self.table, "value")
        if "valid_area_fraction" not in self.table:
            raise ValueError("DriverSeries needs valid-area fractions.")
        fraction = self.table.valid_area_fraction
        if not fraction.between(0, 1).all():
            raise ValueError("Valid-area fractions must be finite and within [0, 1].")


@dataclass
class RequirementSeries:
    table: pd.DataFrame
    name: str
    intended_user: str
    source: str
    status: str = "scenario"
    units: str = "m3/s"
    meaning: str = "river-flow threshold"
    resilience: str = "unknown"

    def __post_init__(self):
        self.table = validate_intervals(self.table, "requirement_m3s")
        if self.units != "m3/s" or (self.table.requirement_m3s.dropna() < 0).any():
            raise ValueError("Requirements must be nonnegative discharge in m3/s.")
        if self.status not in {"scenario", "documented"} or not self.source.strip():
            raise ValueError("Requirement needs scenario/documented status and a source.")


@dataclass(frozen=True)
class AssessmentRequest:
    outlet: Outlet
    start: date
    end: date
    baseline_years: tuple[int, int]
    months: tuple[int, ...] = tuple(range(1, 13))
    water_year_start_month: int = 10
    variables: tuple[str, ...] = ("modis_snow",)
    model: str = "climatology"
    issue_date: date | None = None

    def __post_init__(self):
        if self.start > self.end or (self.end - self.start).days > 365 * 80:
            raise ValueError("Choose an ordered analysis period of at most 80 years.")
        if self.baseline_years[0] > self.baseline_years[1]:
            raise ValueError("Baseline years must be ordered.")
        if not self.months or any(m not in range(1, 13) for m in self.months):
            raise ValueError("Select at least one valid season month.")
        if len(set(self.months)) != len(self.months) or self.water_year_start_month not in range(1, 13):
            raise ValueError("Duplicate months or invalid water-year start.")
        if self.model not in {"climatology", "team"}:
            raise ValueError("Unknown model.")


T = TypeVar("T")


@dataclass
class ProviderResult(Generic[T]):
    status: Status
    message: str
    data: T | None = None
    retry_after_seconds: int | None = None


@dataclass
class ForecastResult:
    status: str
    issue_date: str
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    model: str = "seasonal_climatology"
    training: dict = field(default_factory=dict)
    interval_type: str = "historical variability (10th-90th percentiles); not prediction intervals"
    assumptions: list[str] = field(default_factory=list)
    hindcasts: dict = field(default_factory=dict)


@dataclass
class AssessmentResult:
    request: AssessmentRequest
    flow_status: ProviderResult[FlowSeries]
    driver_status: ProviderResult[DriverSeries]
    observations: pd.DataFrame = field(default_factory=pd.DataFrame)
    baseline: pd.DataFrame = field(default_factory=pd.DataFrame)
    periods: pd.DataFrame = field(default_factory=pd.DataFrame)
    metrics: dict[str, Any] = field(default_factory=dict)
    trends: dict[str, Any] = field(default_factory=dict)
    variability: dict[str, Any] = field(default_factory=dict)
    exposure: dict[str, Any] = field(default_factory=dict)
    forecast: ForecastResult | None = None
    requirement: RequirementSeries | None = None
    limitations: list[str] = field(default_factory=list)
