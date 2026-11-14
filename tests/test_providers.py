import io
import json
from dataclasses import replace
from datetime import date

import httpx
import numpy as np
import pandas as pd
import pytest

from mountain_water.config import Settings
from mountain_water.contracts import Status, validate_intervals
from mountain_water.data.csv_import import import_flow
from mountain_water.data.nasa import MODISProvider
from mountain_water.data.nve import NVEProvider, parse_observations
from mountain_water.data.quality import aggregate_modis_pixels, modis_valid, nve_valid
from mountain_water.data.swiss import SwissProvider, parse_camels
from mountain_water.services.cache import JsonCache, cache_key


def nve_outlet(outlet):
    return replace(outlet, id="nve-test", provider="nve", station_id="2.32.0", calendar_timezone="Etc/GMT-1")


def payload(day="2020-07-01T11:00:00Z", quality=3, correction=0, value=1.):
    return {"data": [{"stationId": "2.32.0", "parameter": 1001, "method": "Mean", "unit": "m3/s",
        "serieVersionNo": 1, "observations": [{"time": day, "value": value,
        "quality": quality, "correction": correction}]}]}


@pytest.mark.parametrize("stamp", ["2020-07-01T11:00:00Z", "2020-02-29T11:00:00Z", "2021-01-01T11:00:00Z"])
def test_nve_fixed_cet_daily_support(outlet, stamp):
    day = pd.Timestamp(stamp).date()
    r = parse_observations(payload(stamp), nve_outlet(outlet), day, day)
    assert r.data.table.start.iloc[0] == pd.Timestamp(stamp) - pd.Timedelta(hours=12)
    assert r.data.table.start.dt.tz_convert("Etc/GMT-1").dt.hour.iloc[0] == 0


def test_nve_quality_zero_and_missing(outlet):
    assert nve_valid(0, 3, 0)
    for correction in (2, 3, 12, 14, 15, 16, 99):
        assert not nve_valid(1, 3, correction)
    for quality in (0, 1, None, 99):
        assert not nve_valid(1, quality, 0)
    r = parse_observations(payload(correction=16), nve_outlet(outlet), date(2020, 7, 1), date(2020, 7, 1))
    assert np.isnan(r.data.table.discharge_m3s.iloc[0])
    assert r.data.table.raw_value.iloc[0] == 1


@pytest.mark.parametrize("code,status", [(401, Status.AUTHENTICATION_REQUIRED), (429, Status.PENDING), (500, Status.ERROR)])
def test_nve_http_statuses(outlet, tmp_path, code, status):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(code, headers={"Retry-After": "30"})))
    p = NVEProvider(Settings(tmp_path, nve_api_key="fixture-not-a-real-key"), client)
    result = p.fetch_flow(nve_outlet(outlet), date(2020, 1, 1), date(2020, 1, 2))
    assert result.status == status
    assert result.data is None
    assert not list(tmp_path.rglob("*.json"))


def test_nve_empty_bad_units_and_credentials(outlet, tmp_path):
    assert NVEProvider(Settings(tmp_path)).fetch_flow(outlet, date(2000, 1, 1), date(2001, 1, 1)).status == Status.AUTHENTICATION_REQUIRED
    assert parse_observations({"data": []}, outlet, date(2000, 1, 1), date(2001, 1, 1)).status == Status.NO_DATA
    data = payload()
    data["data"][0]["unit"] = "mm"
    with pytest.raises(ValueError):
        parse_observations(data, nve_outlet(outlet), date(2020, 1, 1), date(2021, 1, 1))


def test_modis_quality_and_area_weighting():
    assert modis_valid(0, 0, 0)
    assert not modis_valid(250, 0, 0)
    assert not modis_valid(50, 0, 128)
    assert aggregate_modis_pixels([0, 100], [1, 3], [True, True]) == (75, 1)
    assert aggregate_modis_pixels([0, 100], [1, 3], [True, False]) == (None, .25)
    assert aggregate_modis_pixels([0, 100], [1, 1], [True, False]) == (0, .5)
    assert aggregate_modis_pixels([np.nan], [10], [False]) == (None, 0)


def test_nasa_auth_and_missing_geometry(outlet, tmp_path):
    assert MODISProvider(Settings(tmp_path)).fetch_drivers(outlet, date(2020, 1, 1), date(2020, 2, 1)).status == Status.AUTHENTICATION_REQUIRED
    p = MODISProvider(Settings(tmp_path, earth_engine_project="test-project"))
    assert p.fetch_drivers(outlet, date(2020, 1, 1), date(2020, 2, 1)).status == Status.UNSUPPORTED


def test_swiss_schema_missing_and_archive_date_limit(outlet, tmp_path):
    o = replace(outlet, provider="camels_ch", station_id="2263")
    source = io.StringIO("date,discharge_vol(m3/s)\n2020-01-01,0\n2020-01-02,NaN\n")
    result = parse_camels(source, o, date(2020, 1, 1), date(2020, 1, 2), "2026-11-15T00:00:00Z")
    assert result.data.table.valid.tolist() == [True, False]
    assert result.data.table.discharge_m3s.iloc[0] == 0
    assert SwissProvider(Settings(tmp_path)).fetch_flow(o, date(2021, 1, 1), date(2022, 1, 1)).status == Status.NO_DATA
    with pytest.raises(ValueError):
        parse_camels(io.StringIO("date,runoff\n2020-01-01,1"), o, date(2020, 1, 1), date(2020, 1, 2), "2026-11-15T00:00:00Z")


def test_import_contract_rejects_wrong_outlet_units_and_naive_time(flow_factory, outlet):
    from dataclasses import asdict
    f = flow_factory([1])
    meta = {"outlet_id": outlet.id, "calendar_timezone": "UTC", "meaning": "interval_average", "provenance": asdict(f.provenance)}
    imported = import_flow(io.StringIO(f.table.to_csv(index=False)), json.dumps(meta), outlet)
    assert imported.origin == "imported"
    meta["outlet_id"] = "wrong"
    with pytest.raises(ValueError):
        import_flow(io.StringIO(f.table.to_csv(index=False)), json.dumps(meta), outlet)
    t = f.table.copy()
    t["start"] = t.start.dt.tz_localize(None)
    with pytest.raises(ValueError, match="offset"):
        validate_intervals(t, "discharge_m3s")


def test_duplicate_and_overlapping_intervals_rejected(flow_factory):
    t = flow_factory([1, 1]).table
    with pytest.raises(ValueError):
        validate_intervals(pd.concat([t, t]), "discharge_m3s")
    t.loc[0, "end"] += pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match="overlap"):
        validate_intervals(t, "discharge_m3s")


def test_cache_identity_includes_scientific_parameters(tmp_path):
    a = cache_key(provider="NASA", version="061", geometry={"x": 1}, quality="v1", dates="2020")
    assert a != cache_key(provider="NASA", version="061", geometry={"x": 2}, quality="v1", dates="2020")
    cache = JsonCache(tmp_path)
    cache.put(a, {"value": None})
    assert cache.get(a) == {"value": None}
    (tmp_path / (a + ".json")).write_text("broken")
    assert cache.get(a) is None
