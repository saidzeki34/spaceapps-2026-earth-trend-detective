"""Synthetic dataset that mimics the CAMELS-CH layout. Values are invented; only the structure matters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mountain_water.trend.settings import TrendSettings

OBS_HEADER = [
    "date", "discharge_vol(m3/s)", "discharge_spec(mm/d)", "waterlevel(m)", "precipitation(mm/d)",
    "temperature_min(degC)", "temperature_mean(degC)", "temperature_max(degC)", "rel_sun_dur(%)", "swe(mm)",
]

# gauge_id, elevation, area, reservoirs, peak shift (days per decade, negative = earlier), missing share
GAUGES = [
    ("2001", 2200, 80, 0, -6.0, 0.0),
    ("2002", 1900, 150, 0, -3.0, 0.0),
    ("2003", 1700, 300, 0, 0.0, 0.0),
    ("2004", 2500, 40, 0, -8.0, 0.0),
    ("2005", 800, 200, 0, 0.0, 0.0),     # too low -> filtered out
    ("2006", 2100, 120, 3, 0.0, 0.0),    # reservoirs -> filtered out
    ("2007", 2000, 100, 0, 0.0, 0.5),    # too many gaps -> filtered out
]


def _series(gauge_id: str, elev: float, area: float, shift: float, missing: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1981-01-01", "2020-12-31", freq="D")
    years = dates.year.to_numpy() + dates.day_of_year.to_numpy() / 366
    doy = dates.day_of_year.to_numpy()
    decades = (years - 1981) / 10
    peak = 170 + shift * decades
    base = 2 + area / 50
    flow = base * (0.3 + 2.5 * np.exp(-0.5 * ((doy - peak) / 35) ** 2)) * (1 - 0.02 * decades)
    flow *= np.exp(rng.normal(0, 0.15, len(dates)))
    temp = 5 - (elev - 1500) / 200 + 8 * np.sin(2 * np.pi * (doy - 110) / 365) + 0.4 * decades + rng.normal(0, 2, len(dates))
    precip = np.clip(rng.gamma(0.6, 6, len(dates)) - 1, 0, None)
    swe = np.clip(300 * np.cos(2 * np.pi * (doy - 60) / 365) - 50 * decades, 0, None)
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "discharge_vol(m3/s)": flow,
        "discharge_spec(mm/d)": flow * 86.4 / area,
        "waterlevel(m)": 1000 + flow / 10,
        "precipitation(mm/d)": precip,
        "temperature_min(degC)": temp - 4,
        "temperature_mean(degC)": temp,
        "temperature_max(degC)": temp + 4,
        "rel_sun_dur(%)": rng.uniform(20, 60, len(dates)),
        "swe(mm)": swe,
    })
    df.loc[rng.random(len(df)) < 0.002, "discharge_vol(m3/s)"] = np.nan  # scattered short gaps
    if missing:
        n = int(len(df) * missing)
        df.loc[: n - 1, ["discharge_vol(m3/s)", "discharge_spec(mm/d)"]] = np.nan
    df["swe(mm)"] = df["swe(mm)"].where(pd.to_datetime(df["date"]) >= "1998-09-01")  # shorter SWE record
    return df[OBS_HEADER]


def write_fake_camels(root: Path) -> Path:
    base = root / "v0.0" / "extracted" / "camels_ch"
    obs_dir = base / "timeseries" / "observation_based"
    obs_dir.mkdir(parents=True)
    attr_dir = base / "static_attributes"
    attr_dir.mkdir()
    for i, (gid, elev, area, _, shift, missing) in enumerate(GAUGES):
        _series(gid, elev, area, shift, missing, seed=i).to_csv(obs_dir / f"CAMELS_CH_obs_based_{gid}.csv", index=False)
    topo = pd.DataFrame({
        "gauge_id": [g[0] for g in GAUGES],
        "gauge_name": [f"Testbach {g[0]}" for g in GAUGES],
        "water_body_name": ["Testbach"] * len(GAUGES),
        "gauge_lon": np.linspace(6.5, 10, len(GAUGES)),
        "gauge_lat": np.linspace(46.0, 47.0, len(GAUGES)),
        "area": [g[2] for g in GAUGES],
        "elev_mean": [g[1] for g in GAUGES],
        "slope_mean": np.linspace(10, 30, len(GAUGES)),
    })
    # One table with a leading comment line and ';' separator, to exercise the header sniffing.
    with (attr_dir / "CAMELS_CH_topographic_attributes.csv").open("w", encoding="utf-8") as fh:
        fh.write("# synthetic test attributes\n")
        topo.to_csv(fh, index=False, sep=";")
    pd.DataFrame({"gauge_id": [g[0] for g in GAUGES], "num_reservoir": [g[3] for g in GAUGES]}).to_csv(
        attr_dir / "CAMELS_CH_humaninfluence_attributes.csv", index=False
    )
    return base


@pytest.fixture(scope="session")
def fake_raw_dir(tmp_path_factory) -> Path:
    raw = tmp_path_factory.mktemp("camels_raw")
    write_fake_camels(raw)
    return raw


@pytest.fixture(scope="session")
def settings(fake_raw_dir, tmp_path_factory) -> TrendSettings:
    return TrendSettings(raw_dir=fake_raw_dir, processed_dir=tmp_path_factory.mktemp("processed"))


@pytest.fixture(scope="session")
def results(settings):
    from mountain_water.trend import pipeline

    return pipeline.build(settings)
