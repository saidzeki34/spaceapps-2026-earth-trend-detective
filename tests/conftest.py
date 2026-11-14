import numpy as np
import pandas as pd
import pytest

from mountain_water.contracts import FlowSeries, Outlet, Provenance


@pytest.fixture
def outlet():
    return Outlet("test", "Synthetic test outlet", "Test", "synthetic", "TEST", None, None,
                  "none", None, "synthetic", "synthetic", "2000", "2030", "synthetic")


@pytest.fixture
def flow_factory(outlet):
    def make(values, start="2001-01-01", timezone="UTC"):
        dates = pd.date_range(start, periods=len(values), tz=timezone)
        q = np.asarray(values, dtype=float)
        table = pd.DataFrame({"start": dates, "end": dates + pd.Timedelta(days=1),
            "discharge_m3s": q, "valid": np.isfinite(q), "quality": "synthetic"})
        provenance = Provenance("synthetic", "synthetic", "fixture", "1", "2026-11-15T00:00:00Z",
                                "test fixture", "test fixture", "m3/s", "synthetic")
        return FlowSeries(outlet, table, provenance)
    return make
