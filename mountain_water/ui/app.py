"""RivaScope user interface: loading screen, entrance menu and the map explorer.

Run from the repository root with::

    python -m streamlit run mountain_water/ui/app.py

This file only arranges the screens. Selections live in ``state.py``, the
boxes are drawn by the view files, and values come from ``data_source.py``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # started with "streamlit run": make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from mountain_water.ui import controls, elements, overview, prediction_view, risk_view, state, trend_view
from mountain_water.ui.charts import maps

BOX_HEIGHT = 700  # height of the left box, the map area and the right box
TIMELINE_HEIGHT = 142  # space the timeline takes under the map on the river screen
SPLASH_SECONDS = 2.4

# Colours used when the project has not set its own Streamlit theme.
THEME = {
    "base": "dark",
    "primaryColor": "#1a84d8",
    "backgroundColor": "#08111f",
    "secondaryBackgroundColor": "#101d33",
    "textColor": "#e6eef8",
}

CSS = """
<style>
.block-container { padding-top: 2.6rem; padding-bottom: 1rem; max-width: 1900px; }
header[data-testid="stHeader"] { background: transparent; }
iframe[title*="rivascope_map"] { border-radius: 14px; display: block; }

hr { margin: .3rem 0 !important; }
.rs-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.25rem; letter-spacing: .01em; }
.rs-crumbs { display: flex; align-items: center; gap: 8px; height: 100%; font-size: .95rem; opacity: .9; flex-wrap: wrap; }
.rs-crumbs b { font-weight: 600; }
.rs-crumbs .sep { opacity: .45; }

.rs-section { font-size: .72rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; opacity: .62; margin: 2px 0 0; }
.rs-note { font-size: .8rem; line-height: 1.4; opacity: .66; }
.rs-card-head { display: flex; align-items: center; gap: 8px; }
.rs-card-title { font-weight: 600; font-size: .95rem; flex: 1; }
.rs-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
.rs-tag { font-size: .72rem; padding: 2px 8px; border-radius: 999px; background: rgba(128, 136, 150, .2); white-space: nowrap; }
.rs-tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.rs-tile { border-radius: 10px; padding: 8px 12px; background: rgba(128, 136, 150, .13); }
.rs-tile-label { font-size: .74rem; opacity: .7; }
.rs-tile-value { font-size: 1.5rem; font-weight: 700; line-height: 1.25; }
.rs-months { display: grid; grid-template-columns: repeat(6, 1fr); gap: 5px; margin-top: 5px; }
.rs-month { border-radius: 7px; padding: 4px 2px; text-align: center; background: rgba(128, 136, 150, .13); }
.rs-month span { display: block; font-size: .68rem; opacity: .65; }
.rs-month b { font-size: .88rem; font-weight: 600; }
.rs-advice { border-left: 3px solid #f59e0b; padding: 8px 12px; border-radius: 0 8px 8px 0;
  background: rgba(245, 158, 11, .1); font-size: .88rem; line-height: 1.45; }
.rs-pill { display: inline-block; font-size: .78rem; padding: 3px 10px; border-radius: 999px; margin: 0 6px 4px 0;
  background: rgba(56, 189, 248, .16); border: 1px solid rgba(56, 189, 248, .35); }
.rs-pill.pred { background: rgba(253, 224, 71, .14); border-color: rgba(253, 224, 71, .5); }

.rs-timeline-legend { display: flex; justify-content: space-between; gap: 12px; font-size: .8rem; opacity: .85; flex-wrap: wrap; }
.rs-mark { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.rs-mark-data { background: #38bdf8; }
.rs-mark-pred { border: 2px dashed #fde047; width: 7px; height: 7px; }

/* Loading screen */
.rs-splash { position: fixed; inset: 0; z-index: 1000000; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 18px; color: #eaf4ff;
  background: radial-gradient(circle at 50% 38%, #14365f 0%, #08172b 55%, #040b15 100%); }
.rs-splash-logo { animation: rs-pop .9s cubic-bezier(.2, .9, .3, 1.2) both; filter: drop-shadow(0 0 28px rgba(56, 189, 248, .45)); }
.rs-splash-name { font-size: 3rem; font-weight: 700; letter-spacing: .02em; animation: rs-rise .7s .25s ease-out both; }
.rs-splash-name span { color: #7dd3fc; }
.rs-splash-tag { font-size: 1rem; opacity: .75; max-width: 34rem; text-align: center; padding: 0 1rem;
  animation: rs-rise .7s .4s ease-out both; }
.rs-splash-bar { width: 230px; height: 4px; border-radius: 4px; background: rgba(255, 255, 255, .14); overflow: hidden; margin-top: 10px; }
.rs-splash-bar i { display: block; height: 100%; width: 100%; border-radius: 4px; transform-origin: left;
  background: linear-gradient(90deg, #38bdf8, #c9f3ff); animation: rs-load 2.4s .1s ease-in-out both; }
.rs-splash-status { font-size: .8rem; opacity: .6; letter-spacing: .06em; text-transform: uppercase; }
@keyframes rs-pop { from { opacity: 0; transform: scale(.7); } to { opacity: 1; transform: scale(1); } }
@keyframes rs-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes rs-load { from { transform: scaleX(0); } to { transform: scaleX(1); } }

/* Entrance menu */
.rs-hero { border-radius: 22px; padding: 56px 24px 44px; text-align: center; color: #eaf4ff; margin-top: 2vh;
  background: radial-gradient(circle at 50% 0%, #17406f 0%, #0a1b33 60%, #071223 100%);
  border: 1px solid rgba(125, 211, 252, .18); animation: rs-rise .5s ease-out both; }
.rs-hero h1 { font-size: 3.2rem; margin: 14px 0 6px; padding: 0; font-weight: 700; color: #eaf4ff; }
.rs-hero h1 span { color: #7dd3fc; }
.rs-hero p { font-size: 1.1rem; opacity: .8; margin: 0 auto; max-width: 38rem; }
.rs-steps { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 26px; }
.rs-step { font-size: .85rem; padding: 6px 14px; border-radius: 999px; background: rgba(255, 255, 255, .08);
  border: 1px solid rgba(255, 255, 255, .14); }
.rs-step b { color: #7dd3fc; margin-right: 6px; }
</style>
"""


def _apply_default_theme() -> bool:
    """Use RivaScope's colours unless the project already configured a theme.

    Returns True when the colours were set just now, in which case the page
    is drawn again so the browser receives them.
    """
    try:
        from streamlit import config

        if config.get_option("theme.base") is not None or config.get_option("theme.primaryColor") is not None:
            return False
        for name, value in THEME.items():
            config.set_option(f"theme.{name}", value)
        return True
    except Exception:  # noqa: BLE001 - the look is optional; never stop the app because of it
        return False


def _splash() -> None:
    st.html(
        '<div class="rs-splash">'
        f"{elements.logo_img(148, 'rs-splash-logo')}"
        '<div class="rs-splash-name">Riva<span>Scope</span></div>'
        f'<div class="rs-splash-tag">{state.TAGLINE}</div>'
        '<div class="rs-splash-bar"><i></i></div>'
        '<div class="rs-splash-status">Loading</div>'
        "</div>"
    )
    time.sleep(SPLASH_SECONDS)
    state.finish_splash()
    st.rerun()


def _menu() -> None:
    st.html(
        '<div class="rs-hero">'
        f"{elements.logo_img(112)}"
        '<h1>Riva<span>Scope</span></h1>'
        f"<p>{state.TAGLINE}</p>"
        '<div class="rs-steps">'
        '<span class="rs-step"><b>1</b>Pick a country</span>'
        '<span class="rs-step"><b>2</b>Pick a river</span>'
        '<span class="rs-step"><b>3</b>Choose what to see</span>'
        '<span class="rs-step"><b>4</b>Move through the years</span>'
        "</div></div>"
    )
    st.write("")
    _, middle, _ = st.columns([1.3, 1, 1.3])
    with middle:
        st.button(
            "Explore the map", type="primary", width="stretch", on_click=state.start_exploring,
            icon=":material/travel_explore:", key="menu_explore",
        )
        with st.expander("About this version", icon=":material/info:"):
            st.markdown(
                "RivaScope is being built for the NASA Space Apps 2026 challenge "
                "*Earth System Trend Detective*.\n\n"
                "This version is the **interface only**. Norway and Switzerland can be explored on the map. "
                "The plots and assessments have their places on screen, but no measurements, calculations "
                "or predictions are connected yet, so they show empty states.\n\n"
                "Map imagery: Esri World Imagery. Borders and river lines: Natural Earth."
            )


def _top_bar(country: str | None, river: str | None) -> None:
    brand, crumbs, menu = st.columns([1.05, 3.2, 0.75], vertical_alignment="center")
    with brand:
        st.html(f'<div class="rs-brand">{elements.logo_img(30)}<span>{state.APP_NAME}</span></div>')
    with crumbs:
        parts = ["<b>Europe</b>" if not country else "Europe"]
        if country:
            name = maps.countries()[country]
            parts.append(f"<b>{name}</b>" if not river else name)
        if river:
            parts.append(f"<b>{maps.river_name(country, river)}</b>")
        st.html('<div class="rs-crumbs">' + '<span class="sep">›</span>'.join(parts) + "</div>")
    with menu:
        st.button("Menu", key="open_menu", on_click=state.open_menu, icon=":material/home:", width="stretch")


def _results_box(country: str, river: str) -> None:
    """Right box of the river screen: a card for every ticked item."""
    ss = st.session_state
    year, method = ss.year, ss.method
    predicting = state.is_prediction_year(year)
    river_name = maps.river_name(country, river) or ""
    year_label = f"Prediction {year}" if predicting else str(year)

    head, toggle = st.columns([1.5, 1], vertical_alignment="center")
    with head:
        st.subheader("Results", anchor=False)
    with toggle:
        st.toggle(
            "Sample preview",
            value=ss.sample_preview,
            key="w_sample_preview",
            on_change=controls._store,
            args=("sample_preview",),
            help="Fills the plots with made-up shapes so the layout can be judged. They are not data.",
        )
    pill_class = "rs-pill pred" if predicting else "rs-pill"
    method_text = "Per month" if predicting else state.METHODS[method]
    st.html(
        f'<span class="rs-pill">{river_name}</span><span class="{pill_class}">{year_label}</span>'
        f'<span class="rs-pill">{method_text}</span>'
    )
    if ss.sample_preview:
        st.warning("Sample preview is on. The shapes below are made up and are not data.", icon=":material/science:")

    if predicting:
        drew_any = prediction_view.render_prediction_cards(river, year, ss.sample_preview)
    else:
        drew_any = trend_view.render_variable_cards(river, year, method, ss.sample_preview)

    if state.is_selected("risk"):
        drew_any = True
        elements.section_label("Assessments")
        risk_view.render_risk_card(river_name, year_label, ss.sample_preview)
    if state.is_selected("statistics"):
        drew_any = True
        trend_view.render_statistics_card(year)
    if state.is_selected("physical_models"):
        drew_any = True
        prediction_view.render_physical_models_card()

    if not drew_any:
        st.info("Tick a variable or an assessment in the left box to show it here.", icon=":material/checklist:")


def _explore() -> None:
    ss = st.session_state
    valid = maps.valid_ids()
    country, river = ss.country, ss.river
    _top_bar(country, river)

    if river:
        left, centre, right = st.columns([1.05, 2.45, 1.5], gap="small")
    else:
        left, centre = st.columns([1.05, 3.95], gap="small")
        right = None

    with left, st.container(border=True, height=BOX_HEIGHT, gap="xsmall" if river else "small"):
        if river:
            controls.render_characteristics_box(country, river)
        elif country:
            overview.render_river_box(country)
        else:
            overview.render_country_box()

    with centre:
        map_height = BOX_HEIGHT - TIMELINE_HEIGHT if river else BOX_HEIGHT
        event = maps.river_map(country, river, height=map_height)
        if river:
            with st.container(border=True):
                controls.render_timeline()

    if right is not None:
        with right, st.container(border=True, height=BOX_HEIGHT):
            _results_box(country, river)

    if state.consume_map_event(event, valid):
        st.rerun()


def main() -> None:
    theme_just_set = _apply_default_theme()
    st.set_page_config(
        page_title=state.APP_NAME,
        page_icon=str(Path(__file__).resolve().parent / "assets" / "logo.svg"),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    if theme_just_set:
        st.rerun()
    st.html(CSS)
    state.init(maps.valid_ids())

    phase = st.session_state.phase
    if phase == state.PHASE_SPLASH:
        _splash()
    elif phase == state.PHASE_MENU:
        _menu()
    else:
        _explore()


if __name__ == "__main__":
    main()
