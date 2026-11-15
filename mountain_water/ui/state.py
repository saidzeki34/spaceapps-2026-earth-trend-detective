"""Session state, navigation and the catalogue of things a user can select.

Everything the screens need to remember lives here, so that the view files
only draw. Selections are kept in plain session-state entries (not only in
widget keys) because Streamlit forgets a widget's value while the widget is
not on screen, for example while the user is back on the Europe map.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import streamlit as st

APP_NAME = "RivaScope"
TAGLINE = "See how much water mountain rivers carry, when it arrives, and how that changes."

# ---------------------------------------------------------------------------
# Catalogue of selectable items (left box of the river screen)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Variable:
    """One checkbox in the left box that produces one plot in the right box."""

    id: str
    label: str
    unit: str | None  # None: the unit comes from the dataset once one is connected
    group: str  # "reference" or "water"
    color: str
    default: bool = False

    @property
    def label_with_unit(self) -> str:
        return f"{self.label} ({self.unit})" if self.unit else self.label


@dataclass(frozen=True)
class Assessment:
    """One checkbox that adds an assessment card to the right box."""

    id: str
    label: str
    default: bool = False


REFERENCE_VARIABLES: tuple[Variable, ...] = (
    Variable("temperature", "Avg. temperature", "°C", "reference", "#f97316", default=True),
    Variable("precipitation", "Avg. precipitation", None, "reference", "#6366f1"),
    Variable("evaporation", "Avg. evaporation", None, "reference", "#14b8a6"),
    Variable("frozen_water", "Avg. frozen water", None, "reference", "#94a3b8"),
)

WATER_VARIABLES: tuple[Variable, ...] = (
    Variable("discharge", "Discharge", "m³/s", "water", "#0ea5e9", default=True),
    Variable("volume", "Water volume", "m³", "water", "#2563eb"),
)

ASSESSMENTS: tuple[Assessment, ...] = (
    Assessment("risk", "Risk assessment", default=True),
    Assessment("statistics", "Statistics"),
    Assessment("physical_models", "Physical models"),
)

ALL_VARIABLES: tuple[Variable, ...] = WATER_VARIABLES + REFERENCE_VARIABLES

# Calculation method (bottom of the left box).
METHOD_MONTHLY = "monthly"
METHOD_NATIVE = "native"
METHODS: dict[str, str] = {
    METHOD_MONTHLY: "Avg. (monthly average)",
    METHOD_NATIVE: "Shortest interval",
}
METHOD_CAPTIONS: dict[str, str] = {
    METHOD_MONTHLY: "One value per month",
    METHOD_NATIVE: "Finest step the dataset offers",
}

# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

# Provisional until a dataset is connected: each dataset will report its own
# first and last year. 1980 follows the team's UI sketch.
PROVISIONAL_EARLIEST_YEAR = 1980


@dataclass(frozen=True)
class Timeline:
    earliest: int
    latest: int
    provisional: bool = True

    @property
    def prediction(self) -> int:
        """The one-year-ahead prediction sits right after the latest data."""
        return self.latest + 1

    @property
    def years(self) -> list[int]:
        return list(range(self.earliest, self.prediction + 1))


def timeline() -> Timeline:
    return Timeline(earliest=PROVISIONAL_EARLIEST_YEAR, latest=dt.date.today().year)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

PHASE_SPLASH = "splash"
PHASE_MENU = "menu"
PHASE_EXPLORE = "explore"


def init(valid_countries: dict[str, set[str]]) -> None:
    """Create the session entries on the first run of a browser session.

    ``valid_countries`` maps a country code to its river ids. It is used to
    accept a start position from the page address, for example
    ``?country=CH&river=aare&year=2017``, which also skips the intro.
    """
    ss = st.session_state
    if "phase" in ss:
        return
    line = timeline()
    ss.phase = PHASE_SPLASH
    ss.country = None
    ss.river = None
    ss.year = line.latest
    ss.method = METHOD_MONTHLY
    ss.sample_preview = False
    ss.selected = {item.id for item in ALL_VARIABLES + ASSESSMENTS if item.default}
    ss.last_map_seq = None

    params = st.query_params
    country = (params.get("country") or "").upper()
    if country in valid_countries:
        ss.phase = PHASE_EXPLORE
        ss.country = country
        river = (params.get("river") or "").lower()
        if river in valid_countries[country]:
            ss.river = river
    elif params.get("view") in (PHASE_MENU, PHASE_EXPLORE):
        ss.phase = params.get("view")
    year = params.get("year")
    if year and year.isdigit() and int(year) in line.years:
        ss.year = int(year)
    if params.get("preview") == "1":
        ss.sample_preview = True


# Navigation. These are used as button callbacks, so the next run already
# draws the new screen.


def finish_splash() -> None:
    st.session_state.phase = PHASE_MENU


def open_menu() -> None:
    st.session_state.phase = PHASE_MENU


def start_exploring() -> None:
    st.session_state.phase = PHASE_EXPLORE


def show_europe() -> None:
    st.session_state.country = None
    st.session_state.river = None


def select_country(code: str) -> None:
    st.session_state.country = code
    st.session_state.river = None


def show_rivers() -> None:
    st.session_state.river = None


def select_river(river_id: str) -> None:
    st.session_state.river = river_id


def consume_map_event(event: dict | None, valid_countries: dict[str, set[str]]) -> bool:
    """Apply a click that came from the map. Returns True if something changed.

    The map keeps reporting its last click on every run, so each click
    carries a sequence number and is applied only once.
    """
    ss = st.session_state
    if not event or event.get("seq") == ss.last_map_seq:
        return False
    ss.last_map_seq = event.get("seq")
    kind, target = event.get("kind"), event.get("id")
    if kind == "europe":
        show_europe()
    elif kind == "country" and target in valid_countries:
        select_country(target)
    elif kind == "river" and ss.country and target in valid_countries.get(ss.country, set()):
        select_river(target)
    else:
        return False
    return True


# Selections in the left box.


def is_selected(item_id: str) -> bool:
    return item_id in st.session_state.selected


def toggle_selected(item_id: str) -> None:
    """Checkbox callback: mirror the widget into the lasting selection set."""
    if st.session_state.get(f"cb_{item_id}"):
        st.session_state.selected.add(item_id)
    else:
        st.session_state.selected.discard(item_id)


def selected_variables(group: str | None = None) -> list[Variable]:
    return [v for v in ALL_VARIABLES if is_selected(v.id) and (group is None or v.group == group)]


def is_prediction_year(year: int | None = None) -> bool:
    return (st.session_state.year if year is None else year) == timeline().prediction
