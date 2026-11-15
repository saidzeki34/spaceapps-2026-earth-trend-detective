"""The rivers of each country and the state of the data, for the map and the left box.

Reading this takes a while the first time, because the data libraries and the trend section's
tables have to be loaded. The menus do not wait for it: they come from ``controls.catalogue()``.
"""

from __future__ import annotations

from dataclasses import asdict

from mountain_water.ui import data_source


def rivers() -> dict:
    """Every country that can be explored with its rivers, and what data is connected."""
    everything = data_source.rivers()
    return {
        "countries": [
            {"code": code, "name": name, "rivers": [asdict(r) for r in everything if r.country == code]}
            for code, name in data_source.countries().items()
        ],
        "data": data_source.status(),
    }


def river_summary(data: data_source.RiverData) -> dict:
    """Facts about the open river, including the years its timeline covers."""
    return {
        **asdict(data.river),
        "source": data.source,
        "first_year": data.years[0],
        "last_year": data.years[-1],
        "prediction_year": data.prediction_year,
    }
