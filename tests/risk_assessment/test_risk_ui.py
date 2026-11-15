import json
import sys
import types
from pathlib import Path
import pandas as pd
import pytest
from mountain_water.ui import risk_view, server


def test_missing_saved_data(monkeypatch):
    fake = types.ModuleType("mountain_water.ui.backend")
    monkeypatch.setitem(sys.modules, "mountain_water.ui.backend", fake)
    adapter = types.SimpleNamespace(_load=lambda dataset: (None, {"status":"missing", "build_command":"build"}))
    assert risk_view.assessment({"dataset":"ch"}, adapter)["status"] == "missing"


@pytest.mark.parametrize("dataset", ["ch_gldas", "no_gldas", "stations", "unknown"])
def test_model_not_treated_as_river(monkeypatch, dataset):
    fake = types.ModuleType("mountain_water.ui.backend")
    monkeypatch.setitem(sys.modules, "mountain_water.ui.backend", fake)
    with pytest.raises(ValueError):
        risk_view.assessment({"dataset":dataset}, object())


def test_risk_route(monkeypatch):
    monkeypatch.setattr(risk_view, "assessment", lambda query: {"status":"ready", "gauge":query["gauge"]})
    handler = object.__new__(server.Handler)
    handler.path = "/api/risk?dataset=no&gauge=2.13.0"
    handler.server = types.SimpleNamespace(closing_at=1)
    received = []
    handler._json = lambda *args: received.append(args)
    handler.do_GET()
    assert received[0][0]["gauge"] == "2.13.0"


def test_risk_validation_http_status(monkeypatch):
    def invalid(query):
        raise ValueError("Invalid threshold")
    monkeypatch.setattr(risk_view, "assessment", invalid)
    handler = object.__new__(server.Handler)
    handler.path = "/api/risk"
    handler.server = types.SimpleNamespace(closing_at=None)
    received = []
    handler._json = lambda *args: received.append(args)
    handler.do_GET()
    assert received[0][1] == 400


def test_modal_script_injection_and_path_safety(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "WEB_DIR", tmp_path)
    (tmp_path / "index.html").write_text("<body>Original UI</body>")
    handler = object.__new__(server.Handler)
    received = []
    handler._send = lambda *args: received.append(args)
    handler._file("/")
    assert b'Original UI' in received[-1][2]
    assert received[-1][2].count(b'/js/risk.js') == 1
    handler._file("/../outside.txt")
    assert received[-1][0] == 404


def observed_adapter():
    """Synthetic records test the saved-result contract, not real-world findings."""
    daily = pd.DataFrame({
        "date": pd.date_range("1981-10-01", "2020-09-30"),
        "gauge_id": "2.13.0", "discharge_vol": 10., "discharge_vol_filled": False,
    })
    result = types.SimpleNamespace(
        daily=daily, gauges=["2.13.0"],
        meta={"settings": {"hydro_year_start_month": None},
              "provenance": {"description": "synthetic integration fixture"}},
    )
    return types.SimpleNamespace(_load=lambda dataset: (result, {"label": "Synthetic observations"}))


def test_saved_result_contract_and_missing_values_serialize():
    output = risk_view.assessment({"dataset": "no", "gauge": "2.13.0"}, observed_adapter())
    assert output["status"] == "ready"
    assert output["gauge"] == "2.13.0"
    assert output["settings"]["hydro_year_start_month"] == 10
    assert output["xyz_ready"]
    assert output["exposure"] is None
    assert output["provenance"]["description"] == "synthetic integration fixture"
    # Missing leap-day baseline values must be JSON null, never NaN or invented zero.
    assert None in output["hydrograph"]["median"]
    json.dumps(output, allow_nan=False)


@pytest.mark.parametrize("query", [
    {"gauge": "missing"}, {"gauge": "2.13.0", "period": "2000"},
    {"gauge": "2.13.0", "requirement": "nan"},
])
def test_invalid_observed_selection_is_rejected(query):
    with pytest.raises(ValueError):
        risk_view.assessment({"dataset": "no", **query}, observed_adapter())
