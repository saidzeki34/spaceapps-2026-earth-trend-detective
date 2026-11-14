"""One service coordinates validated inputs, providers, numerical analysis and models."""
from dataclasses import replace
from datetime import date

import pandas as pd

from mountain_water.analysis.baseline import build_baseline
from mountain_water.analysis.flow_metrics import calculate_flow_metrics, period_summaries
from mountain_water.analysis.risk import assess_threshold_exposure
from mountain_water.analysis.variability import calculate_variability
from mountain_water.contracts import AssessmentResult, ProviderResult, Status
from mountain_water.models.climatology import SeasonalClimatology
from mountain_water.models.team_model import TeamModel
from mountain_water.models.validation import evaluate_hindcasts


def bounds(request):
    timezone = request.outlet.calendar_timezone
    start = pd.Timestamp(request.start, tz=timezone).tz_convert("UTC")
    end = (pd.Timestamp(request.end, tz=timezone) + pd.Timedelta(days=1)).tz_convert("UTC")
    return start, end


def run_assessment(request, flow_provider=None, driver_provider=None, requirement=None,
                   imported_flow=None, imported_driver=None):
    start = min(request.start, date(request.baseline_years[0], 1, 1))
    end = max(request.end, date(request.baseline_years[1], 12, 31))
    flow_status = (ProviderResult(Status.READY, "Explicit imported observations.", imported_flow)
                   if imported_flow is not None else flow_provider.fetch_flow(request.outlet, start, end)
                   if flow_provider is not None else ProviderResult(Status.NO_DATA, "Choose a provider or import observations."))
    driver_status = ProviderResult(Status.UNSUPPORTED, "No environmental variable requested.")
    if request.variables:
        if imported_driver is not None:
            driver_status = ProviderResult(Status.READY, "Explicit imported environmental series.", imported_driver)
        elif driver_provider:
            driver_status = driver_provider.fetch_drivers(request.outlet, request.start, request.end)
        else:
            driver_status = ProviderResult(Status.NO_DATA, "Choose a NASA provider or documented driver import.")
    result = AssessmentResult(request, flow_status, driver_status, requirement=requirement)
    result.limitations = ["Observed discharge includes historical management; it is not naturalised supply.",
        "Threshold exposure is not service failure or a universal risk score. Resilience is unknown unless documented.",
        "Daily mean deficits cannot establish continuous intraday shortages. Missing periods censor events.",
        "Associations with NASA variables do not establish causes; changing valid-area coverage can change the index.",
        "Scientific interpretations require human review."]
    if flow_status.status != Status.READY:
        return result
    flow = flow_status.data
    if flow.outlet.id != request.outlet.id:
        raise ValueError("Flow outlet does not match the assessment request.")
    if imported_driver is not None and imported_driver.outlet_id != request.outlet.id:
        raise ValueError("Driver outlet does not match the assessment request.")
    begin, finish = bounds(request)
    table = flow.table
    selected = table[(table.start >= begin) & (table.end <= finish)].copy()
    local_months = selected.start.dt.tz_convert(request.outlet.calendar_timezone).dt.month
    seasonal = selected[local_months.isin(request.months)]
    calendar = pd.date_range(request.start, request.end)
    expected = int(calendar.month.isin(request.months).sum()) * 86400
    result.observations = seasonal
    result.metrics = calculate_flow_metrics(seasonal, begin, begin + pd.Timedelta(seconds=expected))
    if requirement:
        result.exposure = assess_threshold_exposure(seasonal, requirement, expected)
    if selected.empty:
        result.limitations.append("No observations fall within the analysis dates. Baseline and forecast may still use reference data.")
    try:
        result.baseline = build_baseline(flow, request.baseline_years)
        analysis_flow = replace(flow, table=selected)
        result.periods = period_summaries(analysis_flow, request.months, request.water_year_start_month)
        reference_table = table[(table.start >= pd.Timestamp(date(request.baseline_years[0], 1, 1),
                                tz=request.outlet.calendar_timezone).tz_convert("UTC")) &
                               (table.end <= pd.Timestamp(date(request.baseline_years[1] + 1, 1, 1),
                                tz=request.outlet.calendar_timezone).tz_convert("UTC"))]
        reference = period_summaries(replace(flow, table=reference_table), request.months,
                                    request.water_year_start_month)
        mean = reference.season_volume_m3.mean() if len(reference) else None
        result.variability = calculate_variability(result.periods, mean)
        result.trends = {"quantity": result.variability["quantity_trend"],
                         "timing": result.variability["timing_trend"]}
        model = TeamModel() if request.model == "team" else SeasonalClimatology()
        issue = request.issue_date or date.today()
        result.forecast = model.fit_predict(flow, issue)
        if request.model == "climatology":
            result.forecast.hindcasts = evaluate_hindcasts(flow)
    except ValueError as exc:
        result.limitations.append(f"Calendar/forecast analysis unavailable: {exc}")
    return result
