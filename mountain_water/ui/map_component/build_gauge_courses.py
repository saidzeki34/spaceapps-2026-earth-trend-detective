"""Build offline gauge-course display geometry from cached OpenStreetMap ways.

Input is a JSON list of {id, country, river, name, lat, lon} gauge metadata.
Without --fetch no network calls occur. --fetch makes one bounded Overpass
query per 30 gauges for river/stream ways within 1.5 km. --network-bbox adds
a small explicit map area so actual upstream tributaries can be retained.
Course anchors require matching names within 150 m; Norway also permits an
unambiguous channel within 25 m, recorded as a position-only display match.
Names and coordinates are source metadata, not a hydrological validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from mountain_water.ui.river_geometry import (
    ATTRIBUTION, COURSES_FILE, LICENSE_URL, MAX_MATCH_DISTANCE_M, MAX_POSITION_ONLY_DISTANCE_M, line_distance_m, name_keys,
)

ENDPOINT = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_M = 1500


def query_for(gauges: list[dict]) -> str:
    if not 1 <= len(gauges) <= 40:
        raise ValueError("Provide 1 to 40 gauges per bounded request.")
    clauses = []
    for gauge in gauges:
        lat, lon = float(gauge["lat"]), float(gauge["lon"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("A gauge has invalid coordinates.")
        clauses.append(f'way["waterway"~"^(river|stream)$"](around:{SEARCH_RADIUS_M},{lat:.7f},{lon:.7f});')
    return '[out:json][timeout:90][maxsize:16777216];(' + "".join(clauses) + ');out tags geom;'


def fetch(gauges: list[dict], cache_dir: Path) -> Path:
    return fetch_query(query_for(gauges), cache_dir)


def fetch_query(query: str, cache_dir: Path) -> Path:
    import requests

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / (hashlib.sha256(query.encode()).hexdigest() + ".json")
    if path.exists():
        return path
    answer = requests.post(ENDPOINT, data={"data": query}, timeout=(15, 120),
                           headers={"User-Agent": "RivaScope-gauge-display/1.0 (cached student map geometry)"})
    answer.raise_for_status()
    payload = answer.json()
    if "elements" not in payload or payload.get("remark"):
        raise ValueError("Overpass returned an incomplete result; it was not cached.")
    payload["rivascope_retrieval"] = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "endpoint": ENDPOINT,
        "query": query,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_ways(paths: list[Path]) -> dict:
    ways = {}
    relations = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for element in payload.get("elements", []):
            if element.get("type") == "relation" and element.get("tags", {}).get("type") == "waterway":
                relations[element["id"]] = element
        for element in payload.get("elements", []):
            if element.get("type") != "way" or element.get("tags", {}).get("waterway") not in {"river", "stream"}:
                continue
            previous = ways.get(element["id"])
            if previous and (previous.get("osm_base_timestamp") or "") > (payload.get("osm3s", {}).get("timestamp_osm_base") or ""):
                continue
            names = []
            for key, value in element.get("tags", {}).items():
                if key in {"name", "alt_name", "loc_name", "official_name", "short_name"} or key.startswith("name:"):
                    names.extend(value.split(";"))
            points = [[p["lon"], p["lat"]] for p in element.get("geometry", []) if "lon" in p and "lat" in p]
            if len(points) < 2:
                continue
            ways[element["id"]] = {
                "id": element["id"], "names": names, "coordinates": points,
                "name_keys": set().union(*(name_keys(n) for n in names)),
                "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
                "retrieved_at": payload.get("rivascope_retrieval", {}).get("retrieved_at"),
                "relation_ids": [], "relation_name_keys": set(),
            }
    for relation_id, relation in relations.items():
        names = [v for k, v in relation.get("tags", {}).items()
                 if k in {"name", "alt_name", "official_name", "loc_name"} or k.startswith("name:")]
        keys = set().union(*(name_keys(n) for n in names))
        for member in relation.get("members", []):
            # Tributary relations are separate rivers. Only explicit main/side
            # channel ways may identify otherwise unnamed lake/bridge sections.
            if member.get("type") == "way" and member.get("role", "") in {"", "main_stream", "side_stream"}:
                way = ways.get(member["ref"])
                if way is not None:
                    way["relation_ids"].append(relation_id)
                    way["relation_name_keys"].update(keys)
    return ways


def network_query(bounds: list[float]) -> str:
    """Fetch a small explicit map area, including source tributary channels."""
    south, west, north, east = bounds
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Use valid south, west, north, east coordinates.")
    if north - south > 1 or east - west > 2:
        raise ValueError("Network requests must be at most 1 degree high and 2 degrees wide.")
    bbox = ','.join(str(v) for v in bounds)
    return ('[out:json][timeout:90][maxsize:33554432];'
            'way["waterway"~"^(river|stream)$"](' + bbox + ');out body geom;')


def nearby_ways(gauge: dict, ways: dict, distance: float) -> list[tuple[float, dict]]:
    """Bounding-box prefilter followed by distance to the original source line."""
    lat, lon = gauge["lat"], gauge["lon"]
    dlat = distance / 111320
    dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
    found = []
    for way in ways.values():
        if "bounds" not in way:
            xs, ys = zip(*way["coordinates"])
            way["bounds"] = min(xs), min(ys), max(xs), max(ys)
        west, south, east, north = way["bounds"]
        if not (west - dlon <= lon <= east + dlon and south - dlat <= lat <= north + dlat):
            continue
        actual = line_distance_m(lat, lon, way["coordinates"])
        if actual <= distance:
            found.append((actual, way))
    return found


def components(ways: list[dict]) -> list[list[dict]]:
    """Group shared OSM vertices; never bridge gaps with invented geometry."""
    by_point = {}
    for i, way in enumerate(ways):
        for point in way["coordinates"]:
            by_point.setdefault(tuple(point), set()).add(i)
    unseen = set(range(len(ways)))
    groups = []
    while unseen:
        pending = [unseen.pop()]
        group = []
        while pending:
            i = pending.pop()
            group.append(ways[i])
            for point in ways[i]["coordinates"]:
                neighbours = by_point[tuple(point)] & unseen
                unseen.difference_update(neighbours)
                pending.extend(neighbours)
        groups.append(group)
    return groups


def upstream_channels(group: list[dict], ways: dict) -> list[dict]:
    """Retain source branches that flow into selected ways at a shared vertex.

    OSM river/stream ways run downstream. Never join endpoints by proximity,
    reverse a way, draw a lake connector, or append another downstream river.
    Coverage remains limited to the cached source ways, not a basin estimate.
    """
    incoming = {}
    for way in ways.values():
        incoming.setdefault(tuple(way["coordinates"][-1]), []).append(way)
    selected = {way["id"]: way for way in group}
    pending = list(group)
    while pending:
        current = pending.pop()
        for point in current["coordinates"]:
            for upstream in incoming.get(tuple(point), []):
                if upstream["id"] not in selected:
                    selected[upstream["id"]] = upstream
                    pending.append(upstream)
    return list(selected.values())


def build(gauges: list[dict], ways: dict) -> dict:
    features, missing = [], {}
    for gauge in gauges:
        gauge_id, country = str(gauge["id"]), str(gauge["country"]).upper()
        river = gauge["river"]
        keys = name_keys(river)
        matching = [w for w in ways.values() if keys & (w["name_keys"] | w.get("relation_name_keys", set()))]
        groups = []
        for group in components(matching):
            distance = min(line_distance_m(gauge["lat"], gauge["lon"], w["coordinates"]) for w in group)
            if distance <= MAX_MATCH_DISTANCE_M:
                groups.append((distance, group))
        groups.sort(key=lambda item: item[0])
        match_method = "provider_name_and_position"
        if not groups and country == "NO":
            # NVE's riverName may name a drainage system, rather than the local
            # channel. Permit an explicitly recorded, tightly bounded spatial
            # display match; never silently relabel the provider's river.
            nearby = sorted(nearby_ways(gauge, ways, MAX_POSITION_ONLY_DISTANCE_M), key=lambda item: (item[0], item[1]["id"]))
            if nearby:
                seed = nearby[0][1]
                seed_keys = seed["name_keys"] | seed.get("relation_name_keys", set())
                candidates = [w for w in ways.values()
                              if w["id"] == seed["id"] or seed_keys & (w["name_keys"] | w.get("relation_name_keys", set()))]
                connected = next(g for g in components(candidates) if seed in g)
                ids = {w["id"] for w in connected}
                # A second unrelated channel within 25 m is not a safe match.
                if not any(w["id"] not in ids for _, w in nearby):
                    groups = [(nearby[0][0], connected)]
                    match_method = "station_position_only"
        if not groups:
            missing[f"{country}:{gauge_id}"] = (
                "No name-matched source channel within 150 m or unambiguous channel within 25 m of this gauge."
                if country == "NO" else "No same-name source waterway was found within 150 m of this gauge.")
            continue
        if len(groups) > 1 and groups[1][0] - groups[0][0] <= 25:
            missing[f"{country}:{gauge_id}"] = "Multiple disconnected same-name waterways are nearby; course matching is ambiguous."
            continue
        distance, group = groups[0]
        relations = {r for w in group for r in w.get("relation_ids", [])}
        if relations:
            # A lake may have no mapped centerline. Keep explicitly related
            # sections as separate lines; never insert a connector across it.
            selected = {w["id"]: w for w in group}
            selected.update({w["id"]: w for w in matching if relations & set(w.get("relation_ids", []))})
            group = list(selected.values())
        group = upstream_channels(group, ways)
        features.append({
            "type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [w["coordinates"] for w in group]},
            "properties": {
                "id": gauge_id, "country": country, "name": gauge.get("name", ""), "river": river,
                "gauge_position": [gauge["lon"], gauge["lat"]],
                "course_source": "OpenStreetMap", "osm_way_ids": sorted(w["id"] for w in group),
                "osm_names": sorted({name for w in group for name in w["names"]}),
                "osm_base_timestamp": sorted({w["osm_base_timestamp"] for w in group if w["osm_base_timestamp"]}),
                "retrieved_at": sorted({w["retrieved_at"] for w in group if w["retrieved_at"]}),
                "match_distance_m": round(distance, 2), "partial_course": True,
                "match_method": match_method,
                "osm_relation_ids": sorted({r for w in group for r in w.get("relation_ids", [])}),
            },
        })
    return {
        "type": "FeatureCollection", "attribution": ATTRIBUTION, "license_url": LICENSE_URL,
        "source_url": "https://www.openstreetmap.org/copyright", "features": features, "missing": missing,
        "method": {"query_radius_m": SEARCH_RADIUS_M, "max_gauge_distance_m": MAX_MATCH_DISTANCE_M,
                   "max_position_only_distance_m": MAX_POSITION_ONLY_DISTANCE_M,
                   "matching": "Provider name/alias or explicit waterway relation and connected OSM vertices. Norway also allows an unambiguous channel within 25 m, labelled station_position_only. Upstream branches follow original downstream-oriented OSM vertices. No invented connectors.",
                   "coordinate_order": "longitude, latitude", "geometry_simplification": "none"},
        "note": "Partial mapped channels and source-connected upstream branches, for display only. Source and mouth are unverified; gaps across lakes are not filled. Not catchments, complete river networks or measurements.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gauges", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--extra-cache", type=Path)
    parser.add_argument("--fetch", action="store_true", help="Fetch bounded gauge batches if they are not already cached")
    parser.add_argument("--network-bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"), help="With --fetch, include channels in this bounded map area")
    parser.add_argument("--output", type=Path, default=COURSES_FILE)
    args = parser.parse_args()
    gauges = json.loads(args.gauges.read_text(encoding="utf-8"))
    if args.fetch:
        for start in range(0, len(gauges), 30):
            fetch(gauges[start:start + 30], args.cache_dir)
    paths = sorted(args.extra_cache.glob("*.json")) if args.extra_cache else []
    paths += sorted(args.cache_dir.glob("*.json"))
    if args.network_bbox and not args.fetch:
        parser.error("--network-bbox requires --fetch; omit both to rebuild from cache")
    if args.network_bbox:
        fetch_query(network_query(args.network_bbox), args.cache_dir)
        paths = (sorted(args.extra_cache.glob("*.json")) if args.extra_cache else []) + sorted(args.cache_dir.glob("*.json"))
    result = build(gauges, load_ways(paths))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Stored {len(result['features'])} source-backed courses; {len(result['missing'])} unavailable.")


if __name__ == "__main__":
    main()
