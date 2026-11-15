"""What a person can choose in RivaScope: occupation, variables, assessments, method.

This file only describes the choices. The numbers come from ``data_source.py``
and the view files; the screens are drawn by the web pages in ``web/``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# ---------------------------------------------------------------------------
# Variables (left box). Each ticked variable becomes one coloured line in the
# shared graph. Variables with the same unit share an axis.
# ---------------------------------------------------------------------------

APP_NAME = "RivaScope"
GROUP_REFERENCE = "reference"
GROUP_WATER = "water"
# Columns of the daily table that are imaginary even for a measured river (no source connected yet).
IMAGINARY_COLUMNS_OF_MEASURED_RIVERS = frozenset({"evap"})


@dataclass(frozen=True)
class Variable:
    id: str
    label: str
    unit: str
    group: str
    color: str
    column: str  # column of the daily table that holds it
    trend_metric: str  # yearly metric of the trend section used in "Statistics"
    explain: str
    as_volume: bool = False  # shown as volume per interval instead of a mean
    default: bool = False


VARIABLES: tuple[Variable, ...] = (
    Variable("temperature", "Avg. temperature", "°C", GROUP_REFERENCE, "#c2532d",
             "temperature_mean", "temp_mean", "Mean air temperature over the catchment.", default=True),
    Variable("precipitation", "Avg. precipitation", "mm/day", GROUP_REFERENCE, "#3f7fb5",
             "precipitation", "precip_total_mm", "Rain and snow falling on the catchment."),
    Variable("evaporation", "Avg. evaporation", "mm/day", GROUP_REFERENCE, "#b48a1f",
             "evap", "evap_total_mm", "Water returning to the air from soil, plants and open water."),
    Variable("frozen_water", "Avg. frozen water", "mm", GROUP_REFERENCE, "#6c94a6",
             "swe", "swe_max_mm", "Snow water equivalent: the water held in the snow pack."),
    Variable("discharge", "Discharge", "m³/s", GROUP_WATER, "#15324f",
             "discharge_vol", "mean_flow", "Water passing the measuring point each second.", default=True),
    Variable("runoff", "Runoff", "mm/day", GROUP_WATER, "#2f8a66",
             "discharge_spec", "runoff_mm", "Discharge spread over the catchment area, comparable with precipitation."),
    Variable("volume", "Water volume", "million m³", GROUP_WATER, "#7a5aa8",
             "discharge_vol", "volume_hm3", "Water that passed during each month or day.", as_volume=True),
)

VARIABLES_BY_ID = {v.id: v for v in VARIABLES}

# ---------------------------------------------------------------------------
# Assessments (left box, shown under the graph)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Assessment:
    id: str
    label: str
    default: bool = False


ASSESSMENTS: tuple[Assessment, ...] = (
    Assessment("risk", "Risk assessment", default=True),
    Assessment("statistics", "Statistics"),
    Assessment("physical", "Physical models"),
)

# ---------------------------------------------------------------------------
# Calculation method (bottom of the left box)
# ---------------------------------------------------------------------------

METHOD_MONTHLY = "monthly"
METHOD_NATIVE = "native"
METHODS = (
    {"id": METHOD_MONTHLY, "label": "Monthly average", "hint": "one value per month"},
    {"id": METHOD_NATIVE, "label": "Shortest interval", "hint": "daily, the finest step of this dataset"},
)

# ---------------------------------------------------------------------------
# Occupations (menu after the loading screen)
#
# Each occupation gets its own question, its own requirement and its own
# selection of long-term changes. The questions and the "needs" for
# hydropower, data centres and government follow the team's project guide
# (audience table and risk design). Power plant and defence are not specified
# there; their wording is a proposal.
#
# No documented requirement exists yet for any of them. Until the risk section
# supplies real ones, each requirement below is an IMAGINARY scenario built
# from the river's own flow record, so that it scales with the river:
#
#   requirement(month) = base + share(month) * long-term mean flow
#
# base is "median" (long-term median flow) or "q347" (the flow reached or
# exceeded on 347 days of an average year, computed by the trend section).
# ---------------------------------------------------------------------------

_ALL_YEAR = (0.0,) * 12


def _months(default: float, **overrides: float) -> tuple[float, ...]:
    names = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return tuple(overrides.get(name, default) for name in names)


@dataclass(frozen=True)
class Occupation:
    id: str
    label: str
    question: str
    requirement_name: str
    requirement_base: str  # "median" or "q347"
    requirement_share: tuple[float, ...]  # share of the mean flow added per month
    requirement_text: str  # plain description of the imaginary scenario
    needs: tuple[str, ...]  # what a real assessment would still need
    focus_metrics: tuple[str, ...]  # yearly metrics of the trend section to report


OCCUPATIONS: tuple[Occupation, ...] = (
    Occupation(
        "hydropower", "Hydropower",
        "How have the amount and the timing of the flow changed?",
        "Design flow", "median", _ALL_YEAR,
        "the river's long-term median flow, all year, standing in for a plant's design flow",
        ("head and turbine limits", "efficiency", "reservoir operation", "power targets"),
        ("volume_hm3", "winter_mean_flow", "summer_mean_flow", "half_volume_doy"),
    ),
    Occupation(
        "data_center", "Data center infrastructure",
        "How dependent would a cooling arrangement be on this river?",
        "Cooling water", "q347", _months(0.05),
        "the low-flow reference Q347 left in the river plus a withdrawal of 5 % of the mean flow, all year",
        ("the cooling design", "water withdrawn, consumed and returned", "restrictions", "a backup supply"),
        ("q95_low", "min7_flow", "days_below_q347", "temp_summer"),
    ),
    Occupation(
        "power_plant", "Power plant",
        "Is there enough river water for cooling, especially in warm, dry months?",
        "Cooling water", "q347", _months(0.15, jun=0.25, jul=0.25, aug=0.25, sep=0.25),
        "the low-flow reference Q347 plus a withdrawal of 15 % of the mean flow, rising to 25 % from June to September",
        ("the cooling type", "water withdrawn and returned", "water-temperature limits", "a backup supply"),
        ("summer_mean_flow", "q95_low", "temp_summer", "low_flow_doy"),
    ),
    Occupation(
        "government", "Government official",
        "Where are water-dependent activities exposed to changing conditions?",
        "Minimum flow", "q347", _ALL_YEAR,
        "the low-flow reference Q347, all year, as used for Swiss minimum-flow rules",
        ("the assets actually affected", "their demand", "their resilience", "the decision at hand"),
        ("days_below_q347", "volume_hm3", "half_volume_doy", "precip_total_mm"),
    ),
    Occupation(
        "defence", "Defence",
        "How dependable is this river as a water source through the year?",
        "Secured supply", "q347", _months(0.02),
        "the low-flow reference Q347 plus a supply of 2 % of the mean flow, all year",
        ("the actual demand", "storage", "alternative sources", "operational plans"),
        ("min7_flow", "cv_daily", "peak_flow", "days_below_q347"),
    ),
)

OCCUPATIONS_BY_ID = {o.id: o for o in OCCUPATIONS}


def catalogue() -> dict:
    """Everything the web pages need to draw the menus. Needs no data, so it is ready at once."""
    return {
        "app": {"name": APP_NAME},
        "variables": [asdict(v) for v in VARIABLES],
        "imaginary_variables": [v.id for v in VARIABLES if v.column in IMAGINARY_COLUMNS_OF_MEASURED_RIVERS],
        "assessments": [asdict(a) for a in ASSESSMENTS],
        "methods": list(METHODS),
        "occupations": [
            {"id": o.id, "label": o.label, "question": o.question} for o in OCCUPATIONS
        ],
    }
