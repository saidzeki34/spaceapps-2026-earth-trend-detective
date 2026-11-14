import io
import json
import zipfile
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd

from mountain_water.contracts import AssessmentRequest, ProviderResult, Status
from mountain_water.models.climatology import SeasonalClimatology
from mountain_water.models.team_model import TeamModel
from mountain_water.models.validation import evaluate_hindcasts
from mountain_water.services.assessment import run_assessment
from mountain_water.services.export import evidence_bundle


def test_forecast_cannot_use_future_observations(flow_factory):
    dates = pd.date_range("2000-01-01", "2010-12-31")
    history = flow_factory(np.where(dates.year < 2008, dates.month, 999.), "2000-01-01")
    forecast = SeasonalClimatology().fit_predict(history, date(2008, 1, 1))
    assert forecast.status == "baseline_only"
    assert len(forecast.table) == 12
    assert forecast.table.estimate_m3s.tolist() == list(range(1, 13))
    changed = history.table.copy()
    changed.loc[changed.start.dt.year >= 2008, "discharge_m3s"] = 50000
    second = SeasonalClimatology().fit_predict(replace(history, table=changed), date(2008, 1, 1))
    pd.testing.assert_frame_equal(forecast.table, second.table)
    assert forecast.interval_type.startswith("historical variability")


def test_hindcast_training_is_chronological(flow_factory):
    dates = pd.date_range("2000-01-01", "2010-12-31")
    history = flow_factory(dates.month, "2000-01-01")
    class InspectModel(SeasonalClimatology):
        def fit_predict(self, train, issue):
            assert (train.table.end <= pd.Timestamp(issue, tz="UTC")).all()
            return super().fit_predict(train, issue)
    evaluation = evaluate_hindcasts(history, InspectModel)
    assert evaluation["n"] == 60
    assert evaluation["mae_m3s"] == 0
    assert evaluation["baseline"]["mae_m3s"] == 0
    assert evaluation["prediction_interval_coverage"] is None


def test_partial_month_is_not_training_evidence(flow_factory):
    dates = pd.date_range("2000-01-01", "2002-12-31")
    flow = flow_factory(np.ones(len(dates)), "2000-01-01")
    table = flow.table.copy()
    table.loc[0, "valid"] = False
    assert SeasonalClimatology().fit_predict(replace(flow, table=table), date(2003, 1, 1)).status == "unavailable"
    assert TeamModel().fit_predict(flow, date(2003, 1, 1)).status == "unavailable"


def test_service_stays_usable_without_credentials(outlet):
    class Unavailable:
        def fetch_flow(self, *args):
            return ProviderResult(Status.AUTHENTICATION_REQUIRED, "Configure provider key.")
    request = AssessmentRequest(outlet, date(2011, 1, 1), date(2020, 12, 31), (2001, 2010))
    result = run_assessment(request, Unavailable())
    assert result.flow_status.status == Status.AUTHENTICATION_REQUIRED
    assert result.driver_status.status == Status.NO_DATA
    assert result.forecast is None
    with zipfile.ZipFile(io.BytesIO(evidence_bundle(result))) as z:
        assert json.loads(z.read("evidence.json"))["flow_status"]["status"] == "authentication_required"


def test_end_to_end_numerical_service_and_evidence(flow_factory):
    dates = pd.date_range("2000-01-01", "2010-12-31")
    flow = flow_factory(np.ones(len(dates)), "2000-01-01")
    request = AssessmentRequest(flow.outlet, date(2005, 1, 1), date(2010, 12, 31), (2000, 2004),
                                water_year_start_month=1, variables=(), issue_date=date(2011, 1, 1))
    result = run_assessment(request, imported_flow=flow)
    assert result.metrics["coverage"] == 1
    assert result.baseline["mean"].dropna().eq(1).all()
    assert result.forecast.status == "baseline_only"
    with zipfile.ZipFile(io.BytesIO(evidence_bundle(result))) as z:
        metadata = json.loads(z.read("evidence.json"))
        assert metadata["flow_status"]["data"]["provenance"]["kind"] == "synthetic"
        assert "NVE_API_KEY" not in z.read("evidence.json").decode()
