"""Plots and tables for the one-year-ahead prediction."""

from __future__ import annotations

import plotly.graph_objects as go

from mountain_water.ui.charts.timeseries import MONTH_NAMES, year_figure
from mountain_water.ui.data_source import KIND_SAMPLE, Series


def prediction_figure(series: Series | None, *, color: str, unit: str | None, height: int = 170) -> go.Figure:
    """Same axes as a measured year, drawn dashed so it is never mistaken for one."""
    return year_figure(
        series, color=color, unit=unit, predicted=True, empty_text="No prediction connected yet", height=height
    )


def monthly_values(series: Series | None) -> list[tuple[str, str]]:
    """Month name and predicted value as text ("—" when not available)."""
    values = ["—"] * 12
    if series is not None and series.kind != KIND_SAMPLE and len(series.values) == 12:
        values = ["—" if v is None else f"{v:.3g}" for v in series.values]
    return list(zip(MONTH_NAMES, values))
