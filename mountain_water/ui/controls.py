"""Controls of the river screen: the characteristics box and the timeline."""

from __future__ import annotations

import streamlit as st

from mountain_water.ui import elements, state
from mountain_water.ui.charts import maps


def _store(name: str) -> None:
    """Widget callback: copy a widget's value into the lasting session entry."""
    st.session_state[name] = st.session_state[f"w_{name}"]


def _checkbox(item_id: str, label: str) -> None:
    st.checkbox(
        label,
        value=state.is_selected(item_id),
        key=f"cb_{item_id}",
        on_change=state.toggle_selected,
        args=(item_id,),
    )


def render_characteristics_box(country: str, river_id: str) -> None:
    """Left box of the river screen: what to show in the right box, and how."""
    st.button("Rivers", key="back_rivers", on_click=state.show_rivers, icon=":material/arrow_back:", type="tertiary")
    st.subheader(maps.river_name(country, river_id) or "River", anchor=False)
    st.caption(f"{maps.countries()[country]} · Characteristics")

    elements.section_label("Reference variables")
    for variable in state.REFERENCE_VARIABLES:
        _checkbox(variable.id, variable.label_with_unit)

    st.divider()
    elements.section_label("Water availability")
    for variable in state.WATER_VARIABLES:
        _checkbox(variable.id, variable.label_with_unit)

    st.divider()
    elements.section_label("Assessments")
    for assessment in state.ASSESSMENTS:
        _checkbox(assessment.id, assessment.label)

    st.divider()
    elements.section_label("Calculation method")
    methods = list(state.METHODS)
    st.radio(
        "Calculation method",
        methods,
        index=methods.index(st.session_state.method),
        format_func=state.METHODS.get,
        captions=[state.METHOD_CAPTIONS[m] for m in methods],
        key="w_method",
        on_change=_store,
        args=("method",),
        label_visibility="collapsed",
    )


def render_timeline() -> None:
    """Year slider under the map: earliest data, latest data, one-year prediction."""
    line = state.timeline()

    def label(year: int) -> str:
        return f"{year} · prediction" if year == line.prediction else str(year)

    st.select_slider(
        "Year",
        options=line.years,
        value=st.session_state.year,
        format_func=label,
        key="w_year",
        on_change=_store,
        args=("year",),
        label_visibility="collapsed",
    )
    provisional = " (provisional until a dataset is connected)" if line.provisional else ""
    st.html(
        '<div class="rs-timeline-legend">'
        f'<span><i class="rs-mark rs-mark-data"></i>{line.earliest} earliest data</span>'
        f'<span><i class="rs-mark rs-mark-data"></i>{line.latest} latest data'
        f'<i class="rs-mark rs-mark-pred" style="margin-left:14px"></i>{line.prediction} one-year prediction</span>'
        "</div>"
        f'<div class="rs-note">Drag to see the results for a year{provisional}.</div>'
    )
