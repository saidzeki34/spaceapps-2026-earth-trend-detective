"""Presentation-contract checks; all values here are synthetic fixtures."""
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mountain_water.trend import pipeline
from mountain_water.ui.backend import Backend, DATASETS


@pytest.fixture
def saved_backend(tmp_path, monkeypatch):
    tables = {name: pd.DataFrame() for name in pipeline.TABLES}
    tables["attributes"] = pd.DataFrame([
        dict(gauge_id="A", name="Gauge A", water_body="River A", lat=46., lon=8., area=40., elevation=1800.),
        dict(gauge_id="UNSELECTED", name="Unselected", water_body="Elsewhere", lat=47., lon=9.),
    ])
    dates = pd.date_range("2019-10-01", "2020-09-30")
    tables["daily"] = pd.DataFrame(dict(gauge_id="A", date=dates, hydro_year=2020,
                                        hydro_doy=np.arange(1, len(dates)+1),
                                        discharge_vol=np.arange(len(dates), dtype=float),
                                        temperature_mean=10.))
    tables["daily"].loc[1, "discharge_vol"] = np.nan
    tables["daily"].loc[tables["daily"].date.dt.month == 11, "temperature_mean"] = np.nan
    tables["annual"] = pd.DataFrame([dict(gauge_id="A", hydro_year=2020, mean_flow=1., volume_hm3=2., temp_mean=10.)])
    tables["trends"] = pd.DataFrame([dict(gauge_id="A", metric="mean_flow", p=np.nan, slope_per_decade=0.)])
    result = pipeline.TrendResults(**tables, meta={"source": "camels_ch", "units": {"discharge_vol": "m3/s", "temperature_mean": "degC"},
                                                  "settings": {"hydro_year_start_month": 10}, "provenance": {"version": "synthetic fixture"}})
    directory = tmp_path / "processed" / "trend"
    directory.mkdir(parents=True)
    for name in pipeline.TABLES: (directory / f"{name}.parquet").touch()
    (directory / "meta.json").write_text("{}")
    monkeypatch.setattr(pipeline, "load", lambda path: result)
    return Backend(tmp_path), result


def test_missing_results_never_create_imaginary_gauges(tmp_path):
    backend = Backend(tmp_path)
    catalogue = backend.catalogue()
    assert {d["id"] for d in catalogue["datasets"]} == set(DATASETS)
    assert all(d["status"] == "missing" and d["gauges"] == [] for d in catalogue["datasets"])
    assert backend.figure({"dataset": "no"})["status"] == "missing"
    assert not list(tmp_path.iterdir())


def test_catalogue_only_exposes_selected_gauges_and_metadata(saved_backend):
    backend, _ = saved_backend
    dataset = backend.catalogue()["datasets"][0]
    assert dataset["status"] == "ready"
    assert [g["id"] for g in dataset["gauges"]] == ["A"]
    assert dataset["gauges"][0]["country"] == "CH"
    assert dataset["provenance"]["version"] == "synthetic fixture"
    assert dataset["years"] == [2020]


def test_daily_table_preserves_missing_values_and_scientific_input(saved_backend):
    backend, result = saved_backend
    before = result.daily.copy(deep=True)
    table = backend.table({"dataset": "ch", "gauge": "A", "year": "2020"})
    assert table["status"] == "ready"
    assert table["rows"][1]["discharge_vol"] is None
    assert table["rows"][0]["discharge_vol"] == 0
    json.dumps(table, allow_nan=False)
    pd.testing.assert_frame_equal(before, result.daily)


def test_multi_axis_monthly_chart_keeps_missing_month(saved_backend):
    backend, result = saved_backend
    fig = backend._timeseries(result, "A", {"variables": "discharge_vol,temperature_mean", "interval": "monthly", "year": "2020"})
    assert len(fig.data) == 2
    assert np.isnan(fig.data[1].y[1])
    response = backend.figure({"variables": "discharge_vol,temperature_mean", "interval": "monthly", "year": "2020"})
    assert response["status"] == "ready"
    assert response["figure"]["data"][0]["connectgaps"] is False
    assert response["figure"]["layout"]["font"]["family"] == "Arial"
    json.dumps(response, allow_nan=False)


def test_missing_model_is_reported_without_substituting_observations(saved_backend):
    backend, _ = saved_backend
    response = backend.figure({"view": "source_regime", "gauge": "A"})
    assert response["status"] == "missing"
    assert response["id"] == "ch_gldas"
    assert "build --source gldas" in response["build_command"]


def test_successful_model_comparison_uses_backend_common_years(saved_backend, monkeypatch):
    backend, observed = saved_backend
    observed.annual = pd.DataFrame(dict(gauge_id="A", hydro_year=np.arange(2000, 2012),
                                       mean_flow=np.arange(1., 13.)))
    model = replace(observed, annual=observed.annual.assign(mean_flow=observed.annual.mean_flow + 2),
                    meta=dict(observed.meta, source="gldas"))
    monkeypatch.setattr(backend, "_paired", lambda dataset: (observed, model, None))
    query = {"view": "source_scatter", "metric": "mean_flow", "gauge": "A"}
    response = backend.figure(query)
    assert response["status"] == "ready"
    comparison = backend.table(query)
    assert comparison["status"] == "ready"
    assert comparison["rows"][0]["n_years"] == 12
    assert comparison["rows"][0]["bias"] == 2
    assert any("not a river measurement or forecast" in note for note in response["notes"])


def test_empty_saved_selection_reports_no_data(saved_backend):
    backend, observed = saved_backend
    observed.annual = observed.annual.iloc[:0]
    response = backend.figure({})
    assert response["status"] == "missing"
    assert "no selected gauges" in response["message"]


@pytest.mark.parametrize("query", [
    {"dataset": "../raw"}, {"gauge": "UNSELECTED"}, {"view": "download"},
    {"variable": "invented"}, {"year": "2050"}, {"interval": "future"},
])
def test_invalid_selections_are_structured_errors(saved_backend, query):
    backend, _ = saved_backend
    assert backend.figure(query)["status"] == "error"


def test_unreadable_saved_build_is_an_error_not_demo_data(tmp_path):
    directory = tmp_path / "processed" / "trend"
    directory.mkdir(parents=True)
    for name in pipeline.TABLES: (directory / f"{name}.parquet").touch()
    (directory / "meta.json").write_text("{}")
    item = Backend(tmp_path).catalogue()["datasets"][0]
    assert item["status"] == "error"
    assert item["gauges"] == []


def test_refresh_invalidates_cached_results(saved_backend):
    backend, _ = saved_backend
    backend.catalogue()
    assert backend._cache
    (backend.data_root / "processed" / "trend" / "daily.parquet").unlink()
    assert backend.refresh()["datasets"][0]["status"] == "missing"
    assert backend._cache == {}
