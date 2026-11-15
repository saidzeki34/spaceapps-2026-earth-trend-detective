"""Right-box cards for a measured year: one plot per ticked variable, and statistics."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from mountain_water.ui import data_source, elements, state
from mountain_water.ui.charts.timeseries import year_figure

GROUP_TITLES = (("water", "Water availability"), ("reference", "Reference variables"))


def render_variable_cards(river_id: str, year: int, method: str, sample_preview: bool) -> bool:
    """Draw a card for each ticked variable. Returns False if none is ticked."""
    drew_any = False
    for group, title in GROUP_TITLES:
        variables = state.selected_variables(group)
        if not variables:
            continue
        drew_any = True
        elements.section_label(f"{title} · {year}")
        for variable in variables:
            series = data_source.get_series(river_id, variable.id, year, method, sample_preview=sample_preview)
            with st.container(border=True):
                elements.card_header(variable.label_with_unit, state.METHODS[method], variable.color)
                elements.plot(year_figure(series, color=variable.color, unit=variable.unit), key=f"plot_{variable.id}")
    return drew_any


def render_statistics_card(year: int) -> None:
    """Table with one row per ticked variable. Values arrive with the trend section."""
    with st.container(border=True):
        elements.card_header("Statistics", str(year))
        variables = state.selected_variables()
        if not variables:
            elements.note("Tick at least one variable to list its statistics.")
            return
        columns = ("Mean", "Min", "Max", "Trend per decade", "p-value")
        table = pd.DataFrame(
            [["—"] * len(columns) for _ in variables],
            index=[v.label_with_unit for v in variables],
            columns=list(columns),
        )
        st.dataframe(table, width="stretch")
        elements.note("No values yet. They will be filled in by the trend section once it is connected.")
