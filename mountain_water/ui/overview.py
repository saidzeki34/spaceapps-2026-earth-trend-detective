"""Left box while the user is still choosing: countries, then rivers."""

from __future__ import annotations

import streamlit as st

from mountain_water.ui import elements, state
from mountain_water.ui.charts import maps


def render_country_box() -> None:
    """Europe map is showing: offer the countries that can be explored."""
    st.subheader("Countries", anchor=False)
    st.caption("Pick a country on the map or here.")
    for code, name in maps.countries().items():
        st.button(
            name,
            key=f"country_{code}",
            on_click=state.select_country,
            args=(code,),
            width="stretch",
            icon=":material/public:",
        )
    elements.note("Only these countries are available for now. The rest of the map is shaded.")


def render_river_box(country: str) -> None:
    """A country is showing: list its significant rivers."""
    st.button("Europe", key="back_europe", on_click=state.show_europe, icon=":material/arrow_back:", type="tertiary")
    st.subheader(maps.countries()[country], anchor=False)
    rivers = maps.rivers(country)
    elements.section_label(f"Significant rivers · {len(rivers)}")
    st.caption("Pick a river on the map or here.")
    for river in rivers:
        st.button(
            river["name"],
            key=f"river_{river['id']}",
            on_click=state.select_river,
            args=(river["id"],),
            width="stretch",
            icon=":material/water:",
        )
    elements.note("River lines and names come from Natural Earth and are simplified for display.")
