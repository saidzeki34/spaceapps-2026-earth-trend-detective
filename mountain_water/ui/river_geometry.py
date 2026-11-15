"""Read source-backed river segments for map display, without network access.

The stored lines are OpenStreetMap waterways matched conservatively to gauge
metadata. They are not complete upstream networks or catchment boundaries.
Missing or changed gauge metadata produces an explicit unavailable result.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

COURSES_FILE = Path(__file__).parent / "web" / "data" / "gauge_courses.geojson"
ATTRIBUTION = "© OpenStreetMap contributors"
LICENSE_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
MAX_MATCH_DISTANCE_M = 150.0


def name_keys(value: str) -> set[str]:
    """Normalize spelling only; parenthesized provider aliases remain usable."""
    value = str(value or "").replace("_", " ")
    parts = [value, re.sub(r"\([^)]*\)", "", value), *re.findall(r"\(([^)]*)\)", value)]
    keys = set()
    for part in parts:
        text = unicodedata.normalize("NFKD", part.casefold())
        key = "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))
        if key:
            keys.add(key)
    return keys


def point_distance_m(lat: float, lon: float, other_lat: float, other_lon: float) -> float:
    """Local map-distance approximation, used only for matching display lines."""
    scale = math.cos(math.radians((lat + other_lat) / 2))
    return 111320 * math.hypot(lat - other_lat, (lon - other_lon) * scale)


def line_distance_m(lat: float, lon: float, coordinates: list) -> float:
    """Distance to the nearest source segment, never to an invented connector."""
    scale = math.cos(math.radians(lat))
    points = [((x - lon) * scale * 111320, (y - lat) * 111320) for x, y in coordinates]
    best = math.inf
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy
        t = max(0, min(1, -(ax * dx + ay * dy) / denominator)) if denominator else 0
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


@lru_cache(maxsize=1)
def _courses() -> dict:
    try:
        return json.loads(COURSES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"features": [], "missing": {}}


def geojson_for_gauges(gauges: list[dict]) -> dict:
    """Return verified source segments and explicit reasons for absent courses.

    Gauge dictionaries use raw ``id``, source ``country``, ``river`` (watercourse
    name), ``name`` (station name), and WGS84 ``lat``/``lon``. Feature IDs match
    those raw IDs; source-file matches additionally require country, name and
    position, so reusing an ID cannot silently show a different watercourse.
    """
    stored = _courses()
    by_id = {(str(f["properties"]["country"]).upper(), str(f["properties"]["id"])): f
             for f in stored.get("features", [])}
    features, missing = [], {}
    for gauge in gauges:
        gauge_id = str(gauge.get("id", ""))
        country = str(gauge.get("country", "")).upper()
        feature = by_id.get((country, gauge_id))
        try:
            lat, lon = float(gauge["lat"]), float(gauge["lon"])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except (KeyError, ValueError, TypeError):
            missing[gauge_id] = "No valid station coordinates are available."
            continue
        if feature is None:
            missing[gauge_id] = stored.get("missing", {}).get(
                f"{country}:{gauge_id}", "No verified river course is stored for this station.")
            continue
        properties = feature["properties"]
        if not name_keys(gauge.get("river", "")) & name_keys(properties["river"]):
            missing[gauge_id] = "The stored course does not match this station's river name."
            continue
        original = properties["gauge_position"]
        if point_distance_m(lat, lon, original[1], original[0]) > MAX_MATCH_DISTANCE_M:
            missing[gauge_id] = "The station position differs from the verified course metadata."
            continue
        distance = min(line_distance_m(lat, lon, line) for line in feature["geometry"]["coordinates"])
        if distance > MAX_MATCH_DISTANCE_M:
            missing[gauge_id] = "No verified river segment lies near this station position."
            continue
        features.append(feature)
    return {
        "type": "FeatureCollection", "features": features, "missing": missing,
        "attribution": ATTRIBUTION, "license_url": LICENSE_URL,
        "source_url": "https://www.openstreetmap.org/copyright",
        "note": "Mapped river segments near gauges; coverage may be partial. Not catchment boundaries.",
    }
