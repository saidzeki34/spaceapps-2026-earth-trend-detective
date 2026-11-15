"""Keep display-map matching conservative and retain source segments."""

from mountain_water.ui import river_geometry as geometry
from mountain_water.ui.map_component.build_gauge_courses import build, query_for


GAUGE = {"id": "12", "country": "CH", "river": "Test River", "name": "Station", "lat": 46.0, "lon": 8.0}


def way(way_id, points, name="Test River"):
    return {
        "id": way_id, "names": [name], "name_keys": geometry.name_keys(name),
        "coordinates": points, "osm_base_timestamp": "2026-11-15T00:00:00Z", "retrieved_at": None,
    }


def test_nearby_wrong_name_is_not_a_course():
    result = build([GAUGE], {1: way(1, [[7.99, 46], [8.01, 46]], "Other River")})
    assert not result["features"]
    assert "CH:12" in result["missing"]


def test_disconnected_distant_same_name_is_not_joined():
    local = [[7.99, 46], [8.01, 46]]
    distant = [[8.3, 46], [8.4, 46]]
    result = build([GAUGE], {1: way(1, local), 2: way(2, distant)})
    feature = result["features"][0]
    assert feature["geometry"]["coordinates"] == [local]
    assert feature["properties"]["osm_way_ids"] == [1]


def test_ambiguous_close_parallel_waterways_stay_unavailable():
    result = build([GAUGE], {
        1: way(1, [[7.99, 46], [8.01, 46]]),
        2: way(2, [[7.99, 46.0001], [8.01, 46.0001]]),
    })
    assert not result["features"]
    assert "ambiguous" in result["missing"]["CH:12"]


def test_connected_ways_retain_exact_source_coordinates():
    a, b = [[7.99, 46], [8, 46]], [[8, 46], [8.01, 46.01]]
    result = build([GAUGE], {1: way(1, a), 2: way(2, b)})
    assert result["features"][0]["geometry"]["coordinates"] == [a, b]


def test_runtime_validates_name_country_and_position(monkeypatch):
    stored = build([GAUGE], {1: way(1, [[7.99, 46], [8.01, 46]])})
    monkeypatch.setattr(geometry, "_courses", lambda: stored)
    assert len(geometry.geojson_for_gauges([GAUGE])["features"]) == 1
    for changed in ({"country": "NO"}, {"river": "Other River"}, {"lat": 47}, {"lon": None}):
        result = geometry.geojson_for_gauges([{**GAUGE, **changed}])
        assert not result["features"]
        assert "12" in result["missing"]


def test_provider_aliases_are_spelling_normalization_not_fuzzy_matching():
    assert geometry.name_keys("Rhone_(Rotten)") & geometry.name_keys("Rhône")
    assert geometry.name_keys("Weisse_Lütschine") & geometry.name_keys("Weisse Lütschine")
    assert not geometry.name_keys("Weisse Lütschine") & geometry.name_keys("Lütschine")


def test_fetch_query_is_bounded_and_uses_actual_waterway_types():
    query = query_for([GAUGE])
    assert '(around:1500,46.0000000,8.0000000)' in query
    assert '["waterway"~"^(river|stream)$"]' in query
    import pytest

    with pytest.raises(ValueError):
        query_for([GAUGE] * 41)
