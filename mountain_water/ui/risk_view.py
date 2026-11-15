"""Right-box card for the risk assessment: index, advice and the volatility plane."""

from __future__ import annotations

import streamlit as st

from mountain_water.ui import elements
from mountain_water.ui.charts.risk import score_bars_figure
from mountain_water.ui.charts.variability import (
    AXIS_QUANTITY,
    AXIS_TIMING,
    AXIS_VARIABILITY,
    volatility_plane_figure,
)

# Where the sample preview puts its point. The position has no meaning.
_SAMPLE_POINT = (0.35, -0.4, 0.6)


def render_risk_card(river_name: str, year_label: str, sample_preview: bool) -> None:
    """Slots for the risk results. Values arrive with the risk_assessment section."""
    with st.container(border=True):
        elements.card_header("Risk assessment", year_label, "#f59e0b")

        elements.value_tiles([("Risk index", "—"), ("p-value", "—")])
        elements.plot(
            score_bars_figure({AXIS_QUANTITY: None, AXIS_TIMING: None, AXIS_VARIABILITY: None}),
            key="plot_risk_scores",
        )

        elements.section_label("Advice")
        st.html(
            '<div class="rs-advice">Advice for this river and year will appear here. '
            "It will be written from the assessed conditions, so it differs between rivers and years.</div>"
        )

        elements.section_label("Volatility plane")
        point = _SAMPLE_POINT if sample_preview else None
        elements.plot(
            volatility_plane_figure(point, is_sample=sample_preview, label=river_name),
            key="plot_volatility_plane",
        )
        elements.note(
            "No results yet. The index, scores, advice and the position in the plane will come from the "
            "risk assessment section once it is connected."
        )
