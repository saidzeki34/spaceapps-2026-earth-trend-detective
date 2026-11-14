from datetime import date

import pandas as pd
import streamlit as st

from mountain_water.analysis.risk import assess_threshold_exposure
from mountain_water.config import Settings, load_outlets
from mountain_water.contracts import AssessmentRequest, RequirementSeries, Status
from mountain_water.data.csv_import import import_driver, import_flow, import_requirement
from mountain_water.data.demo import synthetic_demo
from mountain_water.data.nasa import MODISProvider
from mountain_water.data.nve import NVEProvider
from mountain_water.data.swiss import SwissProvider
from mountain_water.services.assessment import run_assessment
from mountain_water.services.export import evidence_bundle, json_value
from mountain_water.visualization.maps import catchment_map
from mountain_water.visualization.risk import event_figure
from mountain_water.visualization.timeseries import (
    environmental_figure,
    flow_figure,
    outlook_figure,
)
from mountain_water.visualization.variability import comparison_figures, seasonal_figure


def status_message(result):
    if result.status == Status.READY:
        st.caption(result.message)
    elif result.status == Status.ERROR:
        st.error(result.message)
    elif result.status == Status.PENDING:
        st.warning(f"Pending: {result.message}")
    else:
        st.info(f"{result.status.value.replace('_', ' ').capitalize()}: {result.message}")


def number(value, suffix="", digits=1):
    return "Unavailable" if value is None or pd.isna(value) else f"{value:,.{digits}f}{suffix}"


def main():
    st.set_page_config(page_title="Mountain Water | Catchment assessment", page_icon="🏔️", layout="wide")
    st.markdown("""<style>
    .stApp {background:#f7f9fa} .block-container{padding-top:2.4rem;max-width:1440px}
    [data-testid=stSidebar]{background:#eef3f4} h1,h2,h3{color:#153c47}
    [data-testid=stMetric]{background:white;border:1px solid #dce5e8;border-radius:10px;padding:15px}
    </style>""", unsafe_allow_html=True)
    st.caption("NASA SPACE APPS 2026  /  EARTH SYSTEM TREND DETECTIVE")
    st.title("Mountain Water Availability")
    st.write("Follow a river from its catchment to its changing flow. Compare measured water, seasonal history and a clearly defined requirement.")
    settings = Settings.from_env()
    outlets = load_outlets()
    with st.sidebar:
        st.header("Build an assessment")
        mode = st.selectbox("Data route", ["Provider data", "Import CSV", "Developer demo (synthetic)"])
        if mode == "Developer demo (synthetic)":
            outlet = synthetic_demo().outlet
            st.warning("Synthetic data only. No NASA or national measurements.")
        else:
            country = st.selectbox("Country", ["Switzerland", "Norway"])
            choices = [o for o in outlets if o.country == country]
            outlet = st.selectbox("Measured outlet", choices, format_func=lambda o: o.name)
        with st.form("assessment_controls"):
            start = st.date_input("Analysis start", date(2011, 1, 1))
            end = st.date_input("Analysis end", date(2020, 12, 31))
            st.caption("Reference years describe typical history. They are separate from your requirement.")
            baseline_start = st.number_input("Reference first year", 1900, 2100, 2001, step=1)
            baseline_end = st.number_input("Reference last year", 1900, 2100, 2010, step=1)
            season = st.selectbox("Season", ["All months", "Spring (Mar–May)", "Summer (Jun–Aug)",
                                              "Autumn (Sep–Nov)", "Winter (Dec–Feb)"])
            months = {"All months": tuple(range(1, 13)), "Spring (Mar–May)": (3, 4, 5),
                      "Summer (Jun–Aug)": (6, 7, 8), "Autumn (Sep–Nov)": (9, 10, 11),
                      "Winter (Dec–Feb)": (12, 1, 2)}[season]
            water_year = st.selectbox("Water year begins", [10, 1], format_func=lambda m: "October" if m == 10 else "January")
            include_nasa = st.checkbox("Include NASA MODIS snow index", value=mode != "Developer demo (synthetic)")
            st.subheader("Requirement")
            threshold = st.number_input("Example scenario threshold (m³/s)", min_value=0., value=1., step=.1)
            intended_user = st.selectbox("Intended user", ["River ecosystem investigation", "Municipality", "Irrigation", "Hydropower", "Other water-dependent user"])
            st.caption("An adjustable scenario, not an established demand or environmental-flow standard.")
            req_csv = st.file_uploader("Optional time-varying requirement CSV", type="csv", key="req_csv")
            req_meta = st.file_uploader("Requirement metadata JSON", type="json", key="req_meta")
            flow_csv = flow_meta = driver_csv = driver_meta = None
            if mode == "Import CSV":
                flow_csv = st.file_uploader("Observed flow CSV", type="csv")
                flow_meta = st.file_uploader("Flow provenance JSON", type="json")
            if include_nasa:
                driver_csv = st.file_uploader("Optional NASA catchment export CSV", type="csv", key="driver_csv")
                driver_meta = st.file_uploader("Driver provenance JSON", type="json", key="driver_meta")
            model = st.selectbox("Outlook model", ["Seasonal baseline", "Team equation (awaiting formula)"])
            issue = st.date_input("Outlook issue date", date.today())
            submitted = st.form_submit_button("Run assessment", type="primary", width="stretch")
        st.caption("Historical archive: 1981–2020. Live Norwegian flow needs NVE_API_KEY. NASA needs an authorized Earth Engine project.")
    if submitted:
        try:
            request = AssessmentRequest(outlet, start, end, (baseline_start, baseline_end), months,
                water_year, ("modis_snow",) if include_nasa else (),
                "team" if model.startswith("Team") else "climatology", issue)
            imported = None
            if mode == "Developer demo (synthetic)":
                imported = synthetic_demo()
            elif mode == "Import CSV":
                if not flow_csv or not flow_meta:
                    raise ValueError("Supply both the observed flow CSV and provenance JSON.")
                imported = import_flow(flow_csv, flow_meta, outlet)
            if bool(req_csv) != bool(req_meta) or bool(driver_csv) != bool(driver_meta):
                raise ValueError("Each imported CSV needs its matching metadata JSON.")
            if req_csv:
                requirement = import_requirement(req_csv, req_meta)
            else:
                first = pd.Timestamp(min(start, issue), tz=outlet.calendar_timezone).tz_convert("UTC")
                last = (pd.Timestamp(max(end, issue), tz=outlet.calendar_timezone) + pd.DateOffset(years=2)).tz_convert("UTC")
                requirement = RequirementSeries(pd.DataFrame({"start": [first], "end": [last],
                    "requirement_m3s": [threshold]}), f"Example {threshold:g} m³/s threshold", intended_user,
                    "User-defined hypothetical constant threshold; not observed demand")
            imported_driver = import_driver(driver_csv, driver_meta, outlet) if driver_csv else None
            provider = NVEProvider(settings) if outlet.provider == "nve" else SwissProvider(settings)
            with st.spinner("Retrieving evidence and calculating the assessment…"):
                st.session_state.assessment = run_assessment(request, provider, MODISProvider(settings),
                    requirement, imported, imported_driver)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            st.error(f"Assessment inputs could not be used: {exc}")
    result = st.session_state.get("assessment")
    displayed_outlet = result.request.outlet if result else outlet
    st.subheader(displayed_outlet.name)
    if displayed_outlet.provider == "synthetic":
        st.warning("DEVELOPER DEMONSTRATION — every flow value is synthetic. Do not use these results as environmental evidence.")
    left, right = st.columns([1.6, 1])
    with left:
        if displayed_outlet.latitude is not None:
            fig, meta = catchment_map(displayed_outlet)
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Catchment: {meta['source']} · Map tiles © OpenStreetMap contributors")
        else:
            st.info("This synthetic teaching catchment has no real location or boundary.")
    with right:
        st.markdown("**The place behind the numbers**")
        st.write(f"Station **{displayed_outlet.station_id}** · {displayed_outlet.country}")
        st.write(f"Upstream area: **{number(displayed_outlet.catchment_area_km2, ' km²')}**")
        st.write(f"Catalogue coverage: {displayed_outlet.supported_start} to {displayed_outlet.supported_end}")
        st.write(f"Management: {displayed_outlet.regulation_status}")
        st.caption(displayed_outlet.notes)
    if result is None:
        st.info("Choose an outlet and run an assessment. Provider data are retrieved only on request; an explicit CSV import is available if access is blocked.")
        st.markdown("**What you can investigate**\n\nFlow and volume · seasonal timing · threshold exposure · NASA environmental context · a transparent next-year baseline")
        return
    st.caption(f"Results from the last submitted assessment: {result.request.start}–{result.request.end} · "
               f"reference {result.request.baseline_years[0]}–{result.request.baseline_years[1]} · "
               f"season months {result.request.months}. Run again to apply changed controls.")
    status_message(result.flow_status)
    tabs = st.tabs(["Flow & threshold", "Timing & variability", "NASA evidence", "Next-year outlook", "Sources & export"])
    with tabs[0]:
        if result.flow_status.data is not None:
            st.caption(f"Origin: {result.flow_status.data.origin} · retrieved {result.flow_status.data.provenance.retrieved_at}")
        if result.exposure:
            e = result.exposure
            cards = st.columns(4)
            cards[0].metric("Valid time below threshold", number(None if e["below_fraction"] is None else e["below_fraction"] * 100, "%"))
            cards[1].metric("Observed deficit runs", number(e["event_count"], digits=0))
            cards[2].metric("Longest observed run", number(None if e["longest_event_seconds"] is None else e["longest_event_seconds"] / 86400, " days"))
            cards[3].metric("Deficit volume", number(e["deficit_volume_m3"], " m³", 0))
            st.caption(f"Assessed {e['assessed_seconds'] / 86400:,.0f} of {e['expected_seconds'] / 86400:,.0f} selected days "
                       f"({e['coverage']:.1%}). Equality meets the requirement. Gaps censor event boundaries.")
            st.write(f"Requirement: **{result.requirement.name}** · {result.requirement.status} · "
                     f"{result.requirement.intended_user}. Resilience: {result.requirement.resilience}.")
            if e["unresolved_requirement_intervals"]:
                st.warning(f"{e['unresolved_requirement_intervals']} intervals have missing or finer-changing requirements; exposure cannot be resolved there.")
        if not result.observations.empty:
            fig, meta = flow_figure(result)
            st.plotly_chart(fig, width="stretch")
            st.caption(meta.get("band", ""))
            st.write("**Flow** is a rate in m³/s. **Volume** is that rate integrated over time. The historical baseline describes typical past flow; your requirement describes the threshold you want to investigate.")
            st.json(json_value(result.metrics), expanded=False)
            if result.exposure:
                fig, meta = event_figure(result.exposure)
                if fig:
                    st.plotly_chart(fig, width="stretch")
                st.dataframe(pd.DataFrame(result.exposure["events"]), hide_index=True)
    with tabs[1]:
        if result.periods.empty:
            st.info("Complete daily observations are needed for seasonal and water-year metrics.")
        else:
            fig, meta = seasonal_figure(result.periods)
            st.plotly_chart(fig, width="stretch")
            st.caption(meta["completeness"])
            v = result.variability
            st.write("Timing is the day when half of a complete water year's volume has passed. Negative timing change means earlier flow. Variability measures scatter remaining after a trend fit, relative to a fixed positive reference volume.")
            if all(v.get(k) is not None for k in ("quantity_pct_decade", "timing_days_decade", "variability_pct")):
                row = {k: v[k] for k in ("quantity_pct_decade", "timing_days_decade", "variability_pct")}
                row.update(outlet=result.request.outlet.name, years=f"{result.request.start}–{result.request.end}",
                    baseline=str(result.request.baseline_years), season=str(result.request.months),
                    n=v["quantity_trend"]["n"], coverage=result.metrics["coverage"],
                    uncertainty=v["quantity_trend"]["status"], regulation=result.request.outlet.regulation_status)
                signature = str((result.request.start, result.request.end, result.request.baseline_years,
                                 result.request.months, result.request.water_year_start_month,
                                 result.flow_status.data.provenance.kind))
                comparisons = st.session_state.setdefault("comparisons", {})
                comparisons.setdefault(signature, {})[result.request.outlet.id] = row
                points = pd.DataFrame(comparisons[signature].values())
                figures, meta = comparison_figures(points)
                st.plotly_chart(figures[0], width="stretch")
                st.plotly_chart(figures[1], width="stretch")
                st.caption(meta["meaning"] + " Only matching windows, seasons and reference years are compared.")
                st.dataframe(points, hide_index=True)
            else:
                st.info("3D comparison unavailable: at least three complete years and a positive reference volume are needed.")
            st.dataframe(result.periods, hide_index=True)
            st.json(json_value(result.trends), expanded=False)
            st.caption("Trend uncertainty is exploratory. The two-slope adjustment does not cover repeated searches across outlets, seasons or settings. A statistical interval does not establish cause.")
    with tabs[2]:
        status_message(result.driver_status)
        if result.driver_status.data is not None:
            driver = result.driver_status.data
            fig, meta = environmental_figure(driver, result.observations)
            st.plotly_chart(fig, width="stretch")
            st.write(f"**{driver.provenance.identifier}**, version {driver.provenance.version} · nominal resolution {driver.spatial_resolution_m:g} m")
            st.caption(f"{driver.aggregation}. {meta['caution']} Origin: {driver.origin}.")
            st.warning("This is a snow-related spectral index, not snow-water volume or percent snow-covered area. Clouds and conservative screening change the valid area; means below 50% coverage are withheld.")
            st.dataframe(driver.table, hide_index=True)
    with tabs[3]:
        if result.forecast is None:
            st.info("An outlook needs enough usable historical data.")
        else:
            forecast = result.forecast
            st.write(f"**{forecast.status.replace('_', ' ').capitalize()}** · model {forecast.model} · issue {forecast.issue_date}")
            for assumption in forecast.assumptions:
                st.caption(assumption)
            if len(forecast.table):
                fig, _ = outlook_figure(forecast)
                st.plotly_chart(fig, width="stretch")
                st.dataframe(forecast.table, hide_index=True)
                st.json(json_value({"training": forecast.training, "hindcasts": forecast.hindcasts}), expanded=False)
                if result.requirement:
                    ft = forecast.table.rename(columns={"estimate_m3s": "discharge_m3s"}).copy()
                    ft["valid"] = ft.discharge_m3s.notna()
                    exposure = assess_threshold_exposure(ft, result.requirement,
                        (ft.end.max() - ft.start.min()).total_seconds(), allow_events=False)
                    st.write(f"Monthly outlook exposure under **{result.requirement.name}**: "
                             f"{number(exposure['deficit_volume_m3'], ' m³', 0)} deficit; "
                             f"{exposure['coverage']:.0%} assessed coverage.")
                    st.caption(exposure["event_interpretation"] + " This is a scenario calculation, not a shortage probability.")
    with tabs[4]:
        st.markdown("**Evidence and limits**")
        for limitation in result.limitations:
            st.write("• " + limitation)
        if result.flow_status.data:
            st.json(json_value(result.flow_status.data.provenance), expanded=True)
        if result.driver_status.data:
            st.json(json_value(result.driver_status.data.provenance), expanded=False)
        st.download_button("Download evidence bundle", evidence_bundle(result),
                           file_name=f"mountain-water-{result.request.outlet.id}.zip", mime="application/zip")
        st.caption("The bundle contains observations, baseline, period metrics, outlook and full provenance. Credentials are never exported.")
    st.caption("Independent participant project; not affiliated with or endorsed by NASA. Scientific interpretation requires review.")
