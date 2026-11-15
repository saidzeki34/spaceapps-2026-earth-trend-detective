"""Build offline gauge-course display geometry from cached OpenStreetMap ways.

Input is a JSON list of {id, country, river, name, lat, lon} gauge metadata.
Without --fetch no network calls occur. --fetch makes one bounded Overpass
query for river/stream ways within 1.5 km of each supplied gauge (at most 40).
Only same-name, connected waterways within 150 m of the gauge are accepted.
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
    ATTRIBUTION, COURSES_FILE, LICENSE_URL, MAX_MATCH_DISTANCE_M, line_distance_m, name_keys,
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
    import requests

    query = query_for(gauges)
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
        "query": query, "search_radius_m": SEARCH_RADIUS_M,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_ways(paths: list[Path]) -> dict:
    ways = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for element in payload.get("elements", []):
            if element.get("type") != "way" or element.get("tags", {}).get("waterway") not in {"river", "stream"}:
                continue
            names = []
            for key, value in element.get("tags", {}).items():
                if key in {"name", "alt_name", "loc_name", "official_name", "short_name"} or key.startswith("name:"):
                    names.extend(value.split(";"))
            points = [[p["lon"], p["lat"]] for p in element.get("geometry", []) if "lon" in p and "lat" in p]
            if len(points) < 2 or not names:
                continue
            ways[element["id"]] = {
                "id": element["id"], "names": names, "coordinates": points,
                "name_keys": set().union(*(name_keys(n) for n in names)),
                "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
                "retrieved_at": payload.get("rivascope_retrieval", {}).get("retrieved_at"),
            }
    return ways


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


def build(gauges: list[dict], ways: dict) -> dict:
    features, missing = [], {}
    for gauge in gauges:
        gauge_id, country = str(gauge["id"]), str(gauge["country"]).upper()
        river = gauge["river"]
        keys = name_keys(river)
        matching = [w for w in ways.values() if keys & w["name_keys"]]
        groups = []
        for group in components(matching):
            distance = min(line_distance_m(gauge["lat"], gauge["lon"], w["coordinates"]) for w in group)
            if distance <= MAX_MATCH_DISTANCE_M:
                groups.append((distance, group))
        groups.sort(key=lambda item: item[0])
        if not groups:
            missing[f"{country}:{gauge_id}"] = "No same-name source waterway was found within 150 m of this gauge."
            continue
        if len(groups) > 1 and groups[1][0] - groups[0][0] <= 25:
            missing[f"{country}:{gauge_id}"] = "Multiple disconnected same-name waterways are nearby; course matching is ambiguous."
            continue
        distance, group = groups[0]
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
            },
        })
    return {
        "type": "FeatureCollection", "attribution": ATTRIBUTION, "license_url": LICENSE_URL,
        "source_url": "https://www.openstreetmap.org/copyright", "features": features, "missing": missing,
        "method": {"query_radius_m": SEARCH_RADIUS_M, "max_gauge_distance_m": MAX_MATCH_DISTANCE_M,
                   "matching": "Same provider name/alias and connected OSM vertices; ambiguous nearby components excluded.",
                   "coordinate_order": "longitude, latitude", "geometry_simplification": "none"},
        "note": "Partial mapped river segments, for display only. Not catchments, complete river networks or measurements.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gauges", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--extra-cache", type=Path)
    parser.add_argument("--fetch", action="store_true", help="Fetch one bounded query if it is not already cached")
    parser.add_argument("--output", type=Path, default=COURSES_FILE)
    args = parser.parse_args()
    gauges = json.loads(args.gauges.read_text(encoding="utf-8"))
    if args.fetch:
        fetch(gauges, args.cache_dir)
    paths = sorted(args.extra_cache.glob("*.json")) if args.extra_cache else []
    paths += sorted(args.cache_dir.glob("*.json"))
    result = build(gauges, load_ways(paths))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Stored {len(result['features'])} source-backed courses; {len(result['missing'])} unavailable.")


if __name__ == "__main__":
    main()
