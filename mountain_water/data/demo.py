"""Opt-in synthetic developer fixture. Never returned by a real provider."""
import numpy as np
import pandas as pd

from mountain_water.contracts import FlowSeries, Outlet, Provenance, utc_now


def synthetic_demo():
    outlet = Outlet("synthetic-demo", "Synthetic teaching catchment", "Developer demo", "synthetic",
        "SYNTHETIC", None, None, "none", None, "no real geometry", "synthetic fixture",
        "1990-01-01", "2020-12-31", "Synthetic; no real management information")
    dates = pd.date_range("1990-01-01", "2020-12-31", tz="UTC")
    years = dates.year - 1990
    q = 3 + 1.5 * np.sin(2 * np.pi * (dates.dayofyear - 100) / 365.25) + .02 * years
    q = np.asarray(q, dtype=float)
    q[(dates.year == 2017) & (dates.month == 7)] = np.nan
    table = pd.DataFrame({"start": dates, "end": dates + pd.Timedelta(days=1),
                          "discharge_m3s": q, "valid": np.isfinite(q), "quality": "synthetic"})
    provenance = Provenance("Team developer fixture", "synthetic fixture", "synthetic-demo", "1",
        utc_now(), "Project software license", "AI-assisted deterministic developer fixture", "m3/s",
        "synthetic", ("seasonal sinusoid with trend and deliberate missing month; no real measurements",))
    return FlowSeries(outlet, table, provenance, origin="synthetic developer demonstration")
