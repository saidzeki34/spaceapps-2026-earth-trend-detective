"""HTTP boundary checks. Fixtures below are synthetic software-test data only."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mountain_water.ui import server


@pytest.fixture
def http_app(monkeypatch):
    from mountain_water.ui import backend

    monkeypatch.setattr(backend, "catalogue", lambda: {"datasets": [
        {"id": "ch", "status": "missing", "gauges": [], "build_command": "example build"}
    ]})
    monkeypatch.setattr(backend, "figure", lambda query: {
        "status": "ready", "figure": {"data": [{"y": [1, float("nan"), 3]}]}, "query": query
    })
    monkeypatch.setattr(backend, "table", lambda query: {"columns": ["value"], "rows": [{"value": None}]})
    calls = []
    monkeypatch.setattr(backend, "refresh", lambda: calls.append("refresh"))
    app = server.make_server(0)
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{app.server_port}", calls
    app.shutdown()
    app.server_close()
    worker.join(timeout=3)


def get_json(base, path):
    with urlopen(base + path, timeout=15) as response:
        return json.load(response)


def test_missing_catalogue_and_refresh(http_app):
    base, calls = http_app
    item = get_json(base, "/api/catalog")["datasets"][0]
    assert item["status"] == "missing"
    assert item["gauges"] == []
    with urlopen(Request(base + "/api/refresh", data=b"", method="POST"), timeout=15) as response:
        assert json.load(response) == {"ok": True}
    assert calls == ["refresh"]


def test_plotly_and_missing_values_serialize(http_app):
    base, _ = http_app
    data = get_json(base, "/api/figure?dataset=ch&gauge=2268")
    assert data["figure"]["data"][0]["y"] == [1, None, 3]
    assert data["query"] == {"dataset": "ch", "gauge": "2268"}
    assert get_json(base, "/api/table")["rows"][0]["value"] is None
    with urlopen(base + "/vendor/plotly.min.js", timeout=15) as response:
        assert "javascript" in response.headers["Content-Type"]
        assert b"plotly.js" in response.read(1000).lower()


@pytest.mark.parametrize("path", ["/api/view", "/api/outlines", "/api/unknown",
                                    "/%2e%2e/server.py", "/%2e%2e/%2e%2e/README.md"])
def test_obsolete_routes_and_traversal_do_not_leak_files(http_app, path):
    base, _ = http_app
    with pytest.raises(HTTPError) as error:
        urlopen(base + path, timeout=15)
    assert error.value.code == 404


def test_empty_courses_and_bad_dataset(http_app):
    base, _ = http_app
    assert get_json(base, "/api/courses?dataset=ch")["features"] == []
    with pytest.raises(HTTPError) as error:
        urlopen(base + "/api/courses?dataset=unknown", timeout=15)
    assert error.value.code == 404
