"""Right-box cards for the prediction year, and the physical-models card."""

from __future__ import annotations

import streamlit as st

from mountain_water.ui import data_source, elements, state
from mountain_water.ui.charts.prediction import monthly_values, prediction_figure
from mountain_water.ui.trend_view import GROUP_TITLES


def render_prediction_cards(river_id: str, year: int, sample_preview: bool) -> bool:
    """Predicted value per month for each ticked variable. Returns False if none is ticked."""
    drew_any = False
    for group, title in GROUP_TITLES:
        variables = state.selected_variables(group)
        if not variables:
            continue
        drew_any = True
        elements.section_label(f"{title} · predicted for {year}")
        for variable in variables:
            # A prediction is always given per month, whatever the calculation method.
            series = data_source.get_series(
                river_id, variable.id, year, state.METHOD_MONTHLY, predicted=True, sample_preview=sample_preview
            )
            with st.container(border=True):
                elements.card_header(variable.label_with_unit, "Prediction", variable.color)
                elements.plot(
                    prediction_figure(series, color=variable.color, unit=variable.unit),
                    key=f"plot_pred_{variable.id}",
                )
                elements.month_grid(monthly_values(series), unit=variable.unit)
    if drew_any:
        elements.note(
            "A prediction is an estimate for the year after the latest data, one value per month. "
            "It is drawn dashed to keep it apart from measured years."
        )
    return drew_any


def render_physical_models_card() -> None:
    """Reserved for the team's physical flow model."""
    with st.container(border=True):
        elements.card_header("Physical models", "Not available yet", "#a78bfa")
        elements.note(
            "The team's flow model has not been supplied yet. Its equation, inputs and results "
            "will be shown here once the prediction model section provides them."
        )
