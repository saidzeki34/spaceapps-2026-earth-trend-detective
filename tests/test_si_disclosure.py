"""Disclosure must travel with exports without changing scientific values."""

import json

import pandas as pd
import plotly.graph_objects as go
import pytest

from mountain_water.si import disclosure, write_csv, write_figure_html
from mountain_water.trend import pipeline, stations


def test_csv_keeps_values_missingness_and_source_frame(tmp_path):
    original = pd.DataFrame({"flow": [0.0, float("nan"), 1.25], "gauge": ["river", "river", "river"]})
    before = original.copy(deep=True)
    path = tmp_path / "records.csv"
    write_csv(original, path, index=False)
    saved = pd.read_csv(path)
    pd.testing.assert_frame_equal(saved[list(original.columns)], before)
    pd.testing.assert_frame_equal(original, before)
    assert saved["_si_code_assistance"].str.contains("not SI-generated observations").all()
    metadata = json.loads(path.with_suffix(".csv.metadata.json").read_text())
    assert metadata["si_assistance"]["data"]["si_generated_observations"] is False


def test_empty_csv_keeps_disclosure_in_sidecar(tmp_path):
    path = tmp_path / "empty.csv"
    write_csv(pd.DataFrame(columns=["flow"]), path, index=False)
    assert pd.read_csv(path).empty
    assert json.loads(path.with_suffix(".csv.metadata.json").read_text())["si_assistance"]["tools"]


def test_html_credit_preserves_original_figure_and_metadata(tmp_path):
    figure = go.Figure(go.Scatter(x=[1, 2, 3], y=[0, None, 4]))
    figure.layout.meta = {"interpolated_days_hidden": 2}
    before = figure.to_json()
    path = tmp_path / "plot.html"
    write_figure_html(figure, path)
    html = path.read_text(encoding="utf-8")
    assert '<p id="si-disclosure">SI tools assisted' in html
    assert '"si_assistance"' in html
    assert '"interpolated_days_hidden":2' in html
    assert figure.to_json() == before


@pytest.mark.parametrize("module,constructor", [(pipeline, pipeline.TrendResults), (stations, stations.StationNetwork)])
def test_build_metadata_keeps_provider_provenance(tmp_path, module, constructor):
    table = pd.DataFrame({"gauge_id": ["fixture"], "value": [0.0]})
    source = {"source": "synthetic test fixture", "provenance": {"quality": "test only"}}
    result = constructor(**{name: table.copy() for name in module.TABLES}, meta=source.copy())
    result.save(tmp_path)
    metadata = json.loads((tmp_path / "meta.json").read_text())
    assert metadata["provenance"] == source["provenance"]
    assert metadata["si_assistance"]["data"]["test_fixtures"]
    for name in module.TABLES:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / f"{name}.parquet"), table)


def test_disclosure_is_independent_and_does_not_claim_handmade_logo_is_generated():
    first = disclosure()
    first["media"]["logo"]["si_generated"] = True
    assert disclosure()["media"]["logo"]["si_generated"] is False
