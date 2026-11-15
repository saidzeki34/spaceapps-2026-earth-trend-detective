"""The interactive satellite map and the outlines it draws.

The map itself is a small Leaflet page in ``ui/map_component/frontend``.
It shows satellite imagery, shades everything outside the selectable
countries, draws their rivers and reports clicks back to Python.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parents[1] / "map_component" / "frontend"
_component = components.declare_component("rivascope_map", path=str(_FRONTEND))


@st.cache_data(show_spinner=False)
def _catalogue() -> dict[str, dict]:
    """Country names and river names/ids, without the heavy line geometry."""
    data = json.loads((_FRONTEND / "geodata.json").read_text(encoding="utf-8"))
    return {
        code: {
            "name": country["name"],
            "rivers": [{"id": r["id"], "name": r["name"]} for r in data["rivers"].get(code, [])],
        }
        for code, country in data["countries"].items()
    }


def countries() -> dict[str, str]:
    """Country code -> name, for the countries that are lit on the map."""
    return {code: entry["name"] for code, entry in _catalogue().items()}


def rivers(country: str) -> list[dict[str, str]]:
    """Rivers of one country as ``{"id", "name"}``, longest drawn line first."""
    return _catalogue().get(country, {}).get("rivers", [])


def river_name(country: str | None, river_id: str | None) -> str | None:
    for river in rivers(country or ""):
        if river["id"] == river_id:
            return river["name"]
    return None


def valid_ids() -> dict[str, set[str]]:
    """Country code -> set of its river ids (used to check clicks and links)."""
    return {code: {r["id"] for r in entry["rivers"]} for code, entry in _catalogue().items()}


def river_map(country: str | None, river: str | None, *, height: int, key: str = "river_map") -> dict | None:
    """Draw the map and return the user's latest click, if any.

    The click is a dict ``{"kind": "country" | "river" | "europe", "id", "seq"}``.
    """
    return _component(country=country, river=river, height=height, key=key, default=None)
