"""The volatility plane: quantity change, timing change and variability."""

from __future__ import annotations

import plotly.graph_objects as go

AXIS_QUANTITY = "Quantity change"
AXIS_TIMING = "Timing change"
AXIS_VARIABILITY = "Variability"

_GRID = "rgba(128, 136, 150, 0.28)"


def volatility_plane_figure(
    point: tuple[float, float, float] | None = None,
    *,
    is_sample: bool = False,
    label: str = "",
    height: int = 290,
) -> go.Figure:
    """3D view with one point per river and period.

    ``point`` is (quantity change, timing change, variability). Without a
    point the labelled, empty axes are drawn. A sample point only shows where
    a result would sit; its position has no meaning.
    """
    fig = go.Figure()
    if point is not None:
        x, y, z = point
        fig.add_trace(
            go.Scatter3d(
                x=[x], y=[y], z=[z], mode="markers+text",
                marker={"size": 7, "color": "#f59e0b" if is_sample else "#0ea5e9", "line": {"width": 1, "color": "#ffffff"}},
                text=["sample position" if is_sample else label], textposition="top center",
                hovertemplate="sample position<extra></extra>" if is_sample else None,
                showlegend=False,
            )
        )
        # Drop line to the floor so the height is readable.
        fig.add_trace(
            go.Scatter3d(
                x=[x, x], y=[y, y], z=[0, z], mode="lines",
                line={"color": "rgba(128, 136, 150, 0.7)", "width": 3, "dash": "dot"},
                hoverinfo="skip", showlegend=False,
            )
        )
    else:
        # An invisible point keeps the empty axes on screen.
        fig.add_trace(go.Scatter3d(x=[0], y=[0], z=[0], mode="markers", marker={"size": 0.1, "opacity": 0},
                                   hoverinfo="skip", showlegend=False))

    def axis(title: str, value_range: list[float]) -> dict:
        return {
            "title": {"text": title, "font": {"size": 11}}, "range": value_range,
            "showticklabels": point is not None and not is_sample, "tickfont": {"size": 9},
            "gridcolor": _GRID, "zerolinecolor": "rgba(128, 136, 150, 0.6)",
            "showbackground": False, "showline": True, "linecolor": "rgba(128, 136, 150, 0.6)", "nticks": 5,
        }

    fixed = point is None or is_sample
    fig.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        scene={
            "xaxis": axis(AXIS_QUANTITY, [-1, 1] if fixed else None),
            "yaxis": axis(AXIS_TIMING, [-1, 1] if fixed else None),
            "zaxis": axis(AXIS_VARIABILITY, [0, 1] if fixed else None),
            "camera": {"eye": {"x": 1.75, "y": -1.75, "z": 1.05}},
            "aspectmode": "cube",
        },
    )
    return fig
