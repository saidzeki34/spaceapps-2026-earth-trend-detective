"""Display gaps must remain gaps, including seasonal exclusions."""
import pandas as pd

from mountain_water.visualization.timeseries import break_gaps


def test_missing_interval_is_not_drawn_as_continuous_flow():
    table = pd.DataFrame({"start": pd.to_datetime(["2020-01-01", "2020-01-03"], utc=True),
        "end": pd.to_datetime(["2020-01-02", "2020-01-04"], utc=True),
        "discharge_m3s": [1., 3.], "requirement_m3s": [2., 2.], "valid": [True, True]})
    displayed = break_gaps(table)
    assert len(displayed) == 3
    assert pd.isna(displayed.iloc[1].discharge_m3s)
    assert pd.isna(displayed.iloc[1].requirement_m3s)
    assert len(table) == 2
