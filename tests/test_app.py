from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_application_launches_without_credentials(monkeypatch):
    monkeypatch.delenv("NVE_API_KEY", raising=False)
    monkeypatch.delenv("EARTH_ENGINE_PROJECT", raising=False)
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Mountain Water Availability"


def test_synthetic_demo_runs_all_panels():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.selectbox[0].set_value("Developer demo (synthetic)").run()
    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert len(app.tabs) == 5
    assert len(app.metric) == 4
    assert any("synthetic" in w.value.lower() for w in app.warning)
