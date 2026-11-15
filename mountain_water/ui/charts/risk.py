"""Small plot for the risk card: one 0–10 bar per aspect of the assessment."""

from __future__ import annotations

import plotly.graph_objects as go

SCORE_MAX = 10


def score_bars_figure(scores: dict[str, float | None], *, height: int = 118) -> go.Figure:
    """Horizontal bars on a 0–10 scale. A score of None draws an empty track."""
    names = list(scores)
    values = [scores[name] for name in names]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(  # the empty track behind every bar
            y=names, x=[SCORE_MAX] * len(names), orientation="h",
            marker={"color": "rgba(128, 136, 150, 0.16)"}, hoverinfo="skip", showlegend=False,
        )
    )
    fig.add_trace(
        go.Bar(
            y=names, x=[v if v is not None else 0 for v in values], orientation="h",
            marker={"color": "#0ea5e9"},
            text=[f"{v:g}/{SCORE_MAX}" if v is not None else f"—/{SCORE_MAX}" for v in values],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: %{x:g}/10<extra></extra>", showlegend=False,
        )
    )
    fig.update_layout(
        height=height, barmode="overlay", bargap=0.45,
        margin={"l": 4, "r": 48, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"range": [0, SCORE_MAX], "visible": False, "fixedrange": True},
        yaxis={"autorange": "reversed", "fixedrange": True, "tickfont": {"size": 12}},
    )
    return fig
