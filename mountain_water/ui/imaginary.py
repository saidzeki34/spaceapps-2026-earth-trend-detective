"""Imaginary datasets. Nothing in this file is a measurement or a result.

They exist so that every part of the screen has something to show while a
real source is still missing: rivers without data, evaporation, the
prediction, the physical model and the risk index. The interface marks every
value that comes from here as "imaginary". Delete the callers one by one as
the real sources arrive.

The numbers are made up but repeatable: the same river always gets the same
imaginary record.
"""

from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

START = "1981-01-01"
END = "2020-12-31"

# Millimetres of evaporation per day for each degree above freezing. Made up.
_EVAPORATION_PER_DEGREE = 0.22


def _rng(key: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(key.encode("utf-8")))


def make_daily(river_ids: list[str]) -> pd.DataFrame:
    """An imaginary daily record for each river, shaped like the trend section's table.

    A toy snow-and-storage model keeps the columns consistent with each other
    (snow builds up in the cold and melts into the river in spring), so the
    screens behave as they would with real data. It is not a hydrological model.
    """
    dates = pd.date_range(START, END, freq="D")
    day = dates.dayofyear.to_numpy(dtype=float)
    year = dates.year.to_numpy(dtype=float)
    n = len(dates)
    frames = []
    for river_id in river_ids:
        rng = _rng("river|" + river_id)
        mean_temperature = rng.uniform(-1.0, 3.5)
        swing = rng.uniform(8.5, 11.0)
        warming_per_year = rng.uniform(0.25, 0.5) / 10.0
        wetness = rng.uniform(3.0, 5.0)  # mean precipitation, mm/day
        area_km2 = float(np.exp(rng.uniform(np.log(200.0), np.log(3000.0))))
        melt_per_degree = rng.uniform(2.8, 3.8)
        release = rng.uniform(0.03, 0.06)  # share of stored water leaving per day

        shock = rng.normal(0.0, 2.2, n)
        wet = rng.random(n) < 0.45
        amount = rng.gamma(0.9, wetness / (0.45 * 0.9), n)
        season = mean_temperature + warming_per_year * (year - 2000.0) - swing * np.cos(2 * np.pi * (day - 25.0) / 365.25)

        temperature = np.empty(n)
        precipitation = np.where(wet, amount, 0.0)
        snow_pack = np.empty(n)
        evaporation = np.empty(n)
        runoff = np.empty(n)
        weather, snow, ground = 0.0, 60.0, 120.0
        for i in range(n):
            weather = 0.75 * weather + shock[i]
            t = season[i] + weather
            p = precipitation[i]
            snowfall = p if t <= 0.5 else 0.0
            melt = min(snow, max(t, 0.0) * melt_per_degree)
            snow += snowfall - melt
            water = p - snowfall + melt
            lost = min(ground, max(t, 0.0) * _EVAPORATION_PER_DEGREE)
            quick = 0.25 * water
            ground += water - quick - lost
            slow = ground * release
            ground -= slow
            temperature[i], snow_pack[i], evaporation[i], runoff[i] = t, snow, lost, quick + slow

        frames.append(pd.DataFrame({
            "gauge_id": river_id,
            "date": dates,
            "discharge_vol": np.round(runoff * area_km2 / 86.4, 3),  # mm/day over km² -> m³/s
            "discharge_spec": np.round(runoff, 3),
            "precipitation": np.round(precipitation, 2),
            "temperature_mean": np.round(temperature, 2),
            "swe": np.round(snow_pack, 1),
            "evap": np.round(evaporation, 3),
        }))
    return pd.concat(frames, ignore_index=True)


def evaporation(daily: pd.DataFrame) -> pd.Series:
    """Imaginary evaporation for measured rivers, which have no evaporation data yet.

    Made up from the measured air temperature so that it has a believable
    seasonal shape. Where temperature is missing, a plain seasonal curve is used.
    """
    day = daily["date"].dt.dayofyear.to_numpy(dtype=float)
    fallback = 2.0 - 9.0 * np.cos(2 * np.pi * (day - 25.0) / 365.25)
    temperature = daily["temperature_mean"].to_numpy(dtype=float) if "temperature_mean" in daily else fallback
    temperature = np.where(np.isfinite(temperature), temperature, fallback)
    return pd.Series(np.round(np.maximum(temperature, 0.0) * _EVAPORATION_PER_DEGREE, 3), index=daily.index)


def predict_monthly(usual: list[float | None], key: str, additive: bool = False) -> list[float | None]:
    """Imaginary prediction: the river's usual year, nudged month by month."""
    rng = _rng("prediction|" + key)
    out: list[float | None] = []
    for value in usual:
        nudge = rng.normal(0.0, 1.0)
        if value is None:
            out.append(None)
        elif additive:
            out.append(float(value + 0.9 * nudge))
        else:
            out.append(float(max(value * np.exp(0.14 * nudge), 0.0)))
    return out


def model_monthly(reference: list[float | None], key: str) -> tuple[list[float | None], float]:
    """Imaginary output of the (not yet supplied) physical model, and an imaginary agreement score."""
    rng = _rng("model|" + key)
    values = [None if v is None else float(max(v * np.exp(0.16 * rng.normal()), 0.0)) for v in reference]
    return values, round(float(rng.uniform(0.62, 0.9)), 2)


def scores(key: str) -> dict:
    """Imaginary risk index and sub-scores out of 10. No formula has been agreed for them."""
    rng = _rng("scores|" + key)
    quantity, timing, variability = (int(v) for v in rng.integers(1, 9, 3))
    return {
        "quantity": quantity,
        "timing": timing,
        "variability": variability,
        "index": round((quantity + timing + variability) / 3.0, 1),
    }
