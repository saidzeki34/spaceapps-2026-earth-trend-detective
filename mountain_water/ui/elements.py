"""Small shared building blocks for the screens: logo, headers, plots."""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

_ASSETS = Path(__file__).resolve().parent / "assets"
_PLOT_CONFIG = {"displayModeBar": False, "scrollZoom": False}


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    """The logo as an address that can be used in an image tag."""
    encoded = base64.b64encode((_ASSETS / "logo.svg").read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def logo_img(size: int, css_class: str = "") -> str:
    return f'<img src="{logo_data_uri()}" width="{size}" height="{size}" class="{css_class}" alt="RivaScope logo">'


def section_label(text: str) -> None:
    """Small uppercase label that groups cards or checkboxes."""
    st.html(f'<div class="rs-section">{html.escape(text)}</div>')


def card_header(title: str, tag: str = "", color: str | None = None) -> None:
    """Title row of a result card: colour dot, title and a short tag on the right."""
    dot = f'<span class="rs-dot" style="background:{color}"></span>' if color else ""
    tag_html = f'<span class="rs-tag">{html.escape(tag)}</span>' if tag else ""
    st.html(f'<div class="rs-card-head">{dot}<span class="rs-card-title">{html.escape(title)}</span>{tag_html}</div>')


def note(text: str) -> None:
    """Quiet explanatory line under a plot or table."""
    st.html(f'<div class="rs-note">{html.escape(text)}</div>')


def value_tiles(tiles: list[tuple[str, str]]) -> None:
    """A row of label/value tiles, e.g. for an index or a p-value."""
    cells = "".join(
        f'<div class="rs-tile"><div class="rs-tile-label">{html.escape(label)}</div>'
        f'<div class="rs-tile-value">{html.escape(value)}</div></div>'
        for label, value in tiles
    )
    st.html(f'<div class="rs-tiles">{cells}</div>')


def month_grid(values: list[tuple[str, str]], *, unit: str | None) -> None:
    """Twelve small month/value cells, used for the predicted value of each month."""
    cells = "".join(
        f'<div class="rs-month"><span>{html.escape(month)}</span><b>{html.escape(value)}</b></div>'
        for month, value in values
    )
    caption = f"Predicted value per month ({unit})" if unit else "Predicted value per month"
    st.html(f'<div class="rs-note">{html.escape(caption)}</div><div class="rs-months">{cells}</div>')


def plot(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, key=key, config=_PLOT_CONFIG)
