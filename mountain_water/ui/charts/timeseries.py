"""Within-year plots: one variable, one year, months along the bottom."""

from __future__ import annotations

import plotly.graph_objects as go

from mountain_water.ui.data_source import KIND_PREDICTED, KIND_SAMPLE, Series

MONTH_INITIALS = ("J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D")
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
_MUTED = "rgba(128, 136, 150, 0.9)"
_GRID = "rgba(128, 136, 150, 0.18)"


def year_figure(
    series: Series | None,
    *,
    color: str,
    unit: str | None,
    predicted: bool = False,
    empty_text: str = "No data connected yet",
    height: int = 170,
) -> go.Figure:
    """Line plot of one year. Without a series it draws labelled empty axes."""
    fig = go.Figure()
    monthly = series is None or series.method == "monthly"

    if monthly:
        tick_values = list(range(1, 13))
        x_range = [0.5, 12.5]
    else:
        tick_values = [d + 15 for d in _DAYS_BEFORE_MONTH]
        x_range = [0, 366]

    if series is not None:
        count = len(series.values)
        xs = list(range(1, count + 1))
        is_sample = series.kind == KIND_SAMPLE
        dashed = predicted or series.kind == KIND_PREDICTED
        hover_unit = f" {series.unit or unit}" if (series.unit or unit) and not is_sample else ""
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=list(series.values),
                mode="lines+markers" if monthly else "lines",
                line={"color": color, "width": 2.2, "dash": "dash" if dashed else "solid", "shape": "spline" if monthly else "linear"},
                marker={"size": 6, "color": color, "symbol": "circle-open" if dashed else "circle"},
                connectgaps=False,  # a missing value stays a gap, never a zero
                customdata=[MONTH_NAMES[i] for i in range(count)] if monthly else None,
                hovertemplate=(
                    "sample shape<extra></extra>"
                    if is_sample
                    else ("%{customdata}" if monthly else "day %{x}") + ": %{y:.3g}" + hover_unit + "<extra></extra>"
                ),
                showlegend=False,
            )
        )
        if is_sample:
            fig.add_annotation(
                text="SAMPLE SHAPE · NOT DATA",
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                font={"size": 13, "color": "rgba(128, 136, 150, 0.55)"},
            )
    else:
        fig.add_annotation(
            text=empty_text, xref="paper", yref="paper", x=0.5, y=0.55, showarrow=False,
            font={"size": 12.5, "color": _MUTED},
        )

    show_y_numbers = series is not None and series.kind != KIND_SAMPLE
    axis_unit = (series.unit if series is not None and series.unit else unit) or "unit from dataset"
    fig.update_layout(
        height=height,
        margin={"l": 44, "r": 8, "t": 6, "b": 26},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified" if series is not None else False,
        xaxis={
            "range": x_range, "tickmode": "array", "tickvals": tick_values, "ticktext": list(MONTH_INITIALS),
            "showgrid": False, "zeroline": False, "fixedrange": True, "ticks": "outside", "ticklen": 3,
            "linecolor": _GRID, "tickfont": {"size": 11},
        },
        yaxis={
            "title": {"text": axis_unit, "font": {"size": 11, "color": _MUTED}, "standoff": 4},
            "showticklabels": show_y_numbers, "gridcolor": _GRID, "zeroline": False, "fixedrange": True,
            "tickfont": {"size": 10.5}, "nticks": 4,
            "range": None if show_y_numbers else [-0.08, 1.08],
        },
    )
    return fig
