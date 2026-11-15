"""Keep display-map matching conservative and retain source segments."""

from mountain_water.ui import river_geometry as geometry
from mountain_water.ui.map_component.build_gauge_courses import build, query_for, network_query, load_ways


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
    assert geometry.name_keys("Inn / En") & geometry.name_keys("Inn")


def test_fetch_query_is_bounded_and_uses_actual_waterway_types():
    query = query_for([GAUGE])
    assert '(around:1500,46.0000000,8.0000000)' in query
    assert '["waterway"~"^(river|stream)$"]' in query
    import pytest

    with pytest.raises(ValueError):
        query_for([GAUGE] * 41)


def test_branching_channels_retain_original_vertices_and_both_arms():
    trunk = [[7.99, 46], [8, 46]]
    north, south = [[8, 46], [8.01, 46.01]], [[8, 46], [8.01, 45.99]]
    feature = build([GAUGE], {1: way(1, trunk), 2: way(2, north), 3: way(3, south)})['features'][0]
    assert sorted(feature['geometry']['coordinates']) == sorted([trunk, north, south])
    assert feature['properties']['partial_course'] is True


def test_explicit_relation_retains_unnamed_lake_channel_but_not_tributary(tmp_path):
    import json
    a, lake, b = [[7.99, 46], [8, 46]], [[8, 46], [8.01, 46]], [[8.01, 46], [8.02, 46]]
    payload = {'elements': [
        {'type': 'way', 'id': i, 'tags': {'waterway': 'river', **({'name': 'Test River'} if i != 2 else {})},
         'geometry': [{'lon': x, 'lat': y} for x, y in points]}
        for i, points in enumerate([a, lake, b], 1)
    ] + [{'type': 'relation', 'id': 20, 'tags': {'type': 'waterway', 'name': 'Test River'},
          'members': [{'type': 'way', 'ref': 2, 'role': 'main_stream'}]}]}
    path = tmp_path / 'source.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    feature = build([GAUGE], load_ways([path]))['features'][0]
    assert feature['geometry']['coordinates'] == [a, lake, b]
    assert feature['properties']['osm_relation_ids'] == [20]
    payload['elements'][-1]['members'][0]['role'] = 'tributary'
    path.write_text(json.dumps(payload), encoding='utf-8')
    assert build([GAUGE], load_ways([path]))['features'][0]['properties']['osm_way_ids'] == [1]


def test_norwegian_basin_label_can_use_unambiguous_station_position(monkeypatch):
    gauge = {**GAUGE, 'country': 'NO', 'river': 'Drainage system'}
    channel = way(1, [[7.99, 46], [8.01, 46]], 'Local channel')
    stored = build([gauge], {1: channel})
    assert stored['features'][0]['properties']['match_method'] == 'station_position_only'
    assert stored['features'][0]['properties']['river'] == 'Drainage system'
    monkeypatch.setattr(geometry, '_courses', lambda: stored)
    assert len(geometry.geojson_for_gauges([gauge])['features']) == 1
    assert not geometry.geojson_for_gauges([{**gauge, 'lat': 46.0003}])['features']
    nearby = way(2, [[7.99, 46.0001], [8.01, 46.0001]], 'Other channel')
    assert not build([gauge], {1: channel, 2: nearby})['features']
    assert not build([{**gauge, 'lat': 46.0003}], {1: channel})['features']


def test_network_query_is_bounded_and_preserves_source_geometry():
    import pytest
    query = network_query([46.42, 7.78, 46.7, 8.13])
    assert '(46.42,7.78,46.7,8.13)' in query
    assert 'out body geom;' in query
    with pytest.raises(ValueError):
        network_query([40, 0, 60, 30])
    with pytest.raises(ValueError):
        network_query([47, 8, 46, 9])


def test_upstream_tributaries_keep_names_and_do_not_extend_into_downstream_river():
    channel = way(1, [[8, 46], [8.01, 46]])
    left = way(2, [[7.99, 46.01], [8, 46]], 'Left tributary')
    right = way(3, [[7.99, 45.99], [8, 46]], 'Right tributary')
    downstream = way(4, [[8.01, 46], [8.02, 46]], 'Other downstream river')
    feature = build([GAUGE], {w['id']: w for w in [channel, left, right, downstream]})['features'][0]
    assert feature['properties']['osm_way_ids'] == [1, 2, 3]
    assert set(feature['properties']['osm_names']) == {'Test River', 'Left tributary', 'Right tributary'}
    assert len(feature['geometry']['coordinates']) == 3


def test_source_relation_retains_lake_side_sections_without_inventing_connector():
    inlet = way(1, [[7.99, 46], [8, 46]])
    outlet = way(2, [[8.02, 46], [8.03, 46]])
    for channel in [inlet, outlet]:
        channel['relation_ids'] = [30]
        channel['relation_name_keys'] = geometry.name_keys('Test River')
    feature = build([GAUGE], {1: inlet, 2: outlet})['features'][0]
    assert feature['geometry']['coordinates'] == [inlet['coordinates'], outlet['coordinates']]
    assert feature['properties']['partial_course'] is True


def test_newer_source_geometry_wins_independently_of_cache_path_order(tmp_path):
    import json
    paths = []
    for day, end in [('16', 8.02), ('15', 8.01)]:
        path = tmp_path / f'{day}.json'
        path.write_text(json.dumps({'osm3s': {'timestamp_osm_base': f'2026-11-{day}T00:00:00Z'},
            'elements': [{'type': 'way', 'id': 1, 'tags': {'waterway': 'river', 'name': 'Test River'},
                          'geometry': [{'lon': 8, 'lat': 46}, {'lon': end, 'lat': 46}]}]}), encoding='utf-8')
        paths.append(path)
    assert load_ways(paths)[1]['coordinates'][-1] == [8.02, 46]
