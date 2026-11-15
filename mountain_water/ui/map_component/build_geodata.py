"""Build the map geometry file used by the RivaScope map.

This is a one-off developer tool, not part of the running application.
It writes ``mountain_water/ui/web/data/geodata.json`` with:

* the outlines of the countries the map lights up (Norway, Switzerland),
  from public-domain Natural Earth 1:10m data;
* the large rivers of each of those countries. Natural Earth decides which
  rivers are listed and gives a rough line for each. Because that rough line
  sits visibly beside the real river on satellite imagery, the tool then
  replaces it with the detailed course from OpenStreetMap
  (© OpenStreetMap contributors, Open Database License).

One rough Natural Earth line can be several real rivers under one name, so
the rivers are listed as OpenStreetMap knows them, each under its own name;
``source_names`` keeps the Natural Earth name(s) they were found through.

The geometry is for display and selection only. It must not be used as a
catchment boundary, a river length or any other measurement. The list of
rivers still deserves a review by the team against national sources.

Usage (from the repository root)::

    python mountain_water/ui/map_component/build_geodata.py [--source-dir DIR] [--no-osm]

Without ``--source-dir`` the source files are downloaded into a temporary
folder. With it, downloads are kept there and reused (Natural Earth files in
the folder, OpenStreetMap answers in its ``osm`` subfolder). ``--no-osm``
keeps the rough Natural Earth lines and needs only NumPy; the OpenStreetMap
step also needs requests, shapely and pyproj, which the project already uses.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import tempfile
import time
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np

SOURCE_BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
COUNTRY_FILE = "ne_10m_admin_0_countries.geojson"
RIVER_FILES = ("ne_10m_rivers_lake_centerlines.geojson", "ne_10m_rivers_europe.geojson")
OUTPUT = Path(__file__).resolve().parents[1] / "web" / "data" / "geodata.json"

# Countries lit up on the map: code -> Natural Earth ADMIN name.
COUNTRIES = {"NO": "Norway", "CH": "Switzerland"}

# Natural Earth stores Svalbard, Jan Mayen and Bouvet Island inside Norway's
# geometry. The map highlights the mainland and its coastal islands only.
NORWAY_MAINLAND_MIN_LAT = 50.0
NORWAY_MAINLAND_MAX_LAT = 72.0
NORWAY_MAINLAND_MIN_LON = 0.0

# A river is listed for a country when at least this many of its
# Natural Earth vertices lie inside the country outline.
MIN_VERTICES_INSIDE = 20

# Border rivers wander in and out of the generalized outline. Outside
# runs up to this many vertices long, between two inside vertices, are
# kept so that the drawn line stays continuous.
MAX_BRIDGED_VERTICES = 12

# Natural Earth or OpenStreetMap name -> name shown in RivaScope. Only spelling
# variants and local names of the same river are merged here.
DISPLAY_NAMES = {
    "Tana River": "Tana",
    "Teno / Tana / Deatnu": "Tana",
    "Rhein": "Rhine",
    "Rhin": "Rhine",
    "Rhne": "Rhône",
    "Le Rhône": "Rhône",
    "Klarlven": "Trysilelva (Klarälven)",
    "Klarälven": "Trysilelva (Klarälven)",
    "Patsoyoki": "Pasvikelva",
    "Paatsjoki / Pasvikelva / Патсойоки": "Pasvikelva",
}

COORD_DECIMALS = 4

# --- Detailed river courses from OpenStreetMap -----------------------------
OVERPASS_URLS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
# OpenStreetMap waterways this close to the rough line are fetched and may be used.
OSM_SEARCH_RADIUS_M = 3000
# A named OpenStreetMap river counts as the same river when at least
# OSM_MIN_SHARED_M of it runs within OSM_SAME_RIVER_RADIUS_M of the rough line.
# Tributaries only come that close where they join, so they stay out.
OSM_SAME_RIVER_RADIUS_M = 1200
OSM_MIN_SHARED_M = 8000
OSM_SIMPLIFY_M = 12  # drawing tolerance, about one screen pixel at the closest zoom
OSM_MIN_PIECE_M = 250
OSM_COORD_DECIMALS = 5
# An OpenStreetMap river is listed when at least this much of it follows a listed rough line.
OSM_MIN_LISTED_KM = 25
OSM_METRIC_CRS = "EPSG:3035"  # an equal-area European grid in metres, for distances and lengths


def load(source_dir: Path, name: str) -> dict:
    path = source_dir / name
    if not path.exists():
        print(f"downloading {name}")
        urllib.request.urlretrieve(SOURCE_BASE_URL + name, path)  # fixed https address
    return json.loads(path.read_text(encoding="utf-8"))


def polygon_parts(geometry: dict) -> list:
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return [geometry["coordinates"]]


def points_in_ring(xs: np.ndarray, ys: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Even-odd rule test of many points against one closed ring."""
    inside = np.zeros(xs.shape, dtype=bool)
    for (ax, ay), (bx, by) in itertools.pairwise(ring):
        if ay == by:
            continue
        crosses = ((ay > ys) != (by > ys)) & (xs < (bx - ax) * (ys - ay) / (by - ay) + ax)
        inside ^= crosses
    return inside


def points_in_country(xs: np.ndarray, ys: np.ndarray, parts: list) -> np.ndarray:
    inside = np.zeros(xs.shape, dtype=bool)
    for part in parts:
        outer = part[0]
        min_x, min_y = outer.min(axis=0)
        max_x, max_y = outer.max(axis=0)
        candidates = (xs >= min_x) & (xs <= max_x) & (ys >= min_y) & (ys <= max_y) & ~inside
        if not candidates.any():
            continue
        hit = points_in_ring(xs[candidates], ys[candidates], outer)
        for hole in part[1:]:
            hit &= ~points_in_ring(xs[candidates], ys[candidates], hole)
        inside[np.flatnonzero(candidates)[hit]] = True
    return inside


def kept_runs(inside: np.ndarray) -> list[tuple[int, int]]:
    """Index ranges (start, end exclusive) of a line to draw for a country."""
    keep = inside.copy()
    indices = np.flatnonzero(inside)
    for a, b in itertools.pairwise(indices):
        if 1 < b - a <= MAX_BRIDGED_VERTICES + 1:
            keep[a:b] = True
    runs = []
    start = None
    for i, flag in enumerate(keep):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(keep)))
    # One extra vertex at each end so the line reaches the border.
    return [(max(a - 1, 0), min(b + 1, len(keep))) for a, b in runs]


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def length_km(line: list) -> float:
    total = 0.0
    for (lon1, lat1, *_), (lon2, lat2, *_) in itertools.pairwise(line):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
        h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
        total += 2 * 6371.0 * math.asin(math.sqrt(h))
    return total


def to_latlon(line: list) -> list[list[float]]:
    return [[round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)] for lon, lat, *_ in line]


def bounds_of(lines: list) -> list[list[float]]:
    lats = [p[0] for line in lines for p in line]
    lons = [p[1] for line in lines for p in line]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def overpass_query(lines: list) -> str:
    """Ask for every river or canal way near the rough line, and the river relations they belong to."""
    from shapely.geometry import LineString

    parts = []
    for line in lines:
        if len(line) < 2:
            continue
        simple = LineString([(lon, lat) for lat, lon in line]).simplify(0.008)
        coords = ",".join(f"{lat:.4f},{lon:.4f}" for lon, lat in simple.coords)
        parts.append(f'way["waterway"~"^(river|canal)$"](around:{OSM_SEARCH_RADIUS_M},{coords});')
    return f'[out:json][timeout:240];({"".join(parts)});out tags geom;rel(bw)["waterway"];out body;'


def overpass_query_light(lines: list) -> str:
    """A cheaper question for when the service refuses the full one.

    It finds the river relations that pass near sample points of the rough line, and returns their
    ways inside the line's bounding box. Rivers that have no relation are only partly covered.
    """
    from shapely.geometry import LineString

    points, lats, lons = [], [], []
    for line in lines:
        if len(line) < 2:
            continue
        rough = LineString([(lon, lat) for lat, lon in line])
        count = max(2, int(rough.length / 0.12) + 1)
        points += [rough.interpolate(i / (count - 1), normalized=True) for i in range(count)]
        lats += [lat for lat, _ in line]
        lons += [lon for _, lon in line]
    near = "".join(f'way["waterway"="river"](around:1500,{q.y:.4f},{q.x:.4f});' for q in points)
    box = f"{min(lats) - 0.05:.3f},{min(lons) - 0.05:.3f},{max(lats) + 0.05:.3f},{max(lons) + 0.05:.3f}"
    return (f'[out:json][timeout:120];({near})->.near;rel(bw.near)["waterway"="river"]->.r;.r out body;'
            f"(way(r.r)({box});.near;);out tags geom;")


def fetch_osm(cache_dir: Path, key: str, lines: list) -> list[dict]:
    """OpenStreetMap elements near one river. Answers are kept in ``cache_dir`` and reused."""
    import requests

    cache = cache_dir / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["elements"]
    for attempt in range(6):
        query = overpass_query(lines) if attempt < 2 else overpass_query_light(lines)
        try:
            answer = requests.post(OVERPASS_URLS[attempt % len(OVERPASS_URLS)], data={"data": query},
                                   headers={"User-Agent": "river-outline-builder/1.0"}, timeout=300)
            if answer.status_code == 200 and answer.text.lstrip().startswith("{"):
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache.write_text(answer.text, encoding="utf-8")
                return answer.json()["elements"]
        except requests.RequestException:
            pass
        time.sleep(20 + 20 * attempt)  # the public service asks clients to wait when it is busy
    return []


def _line_parts(geometry) -> list:
    """The plain lines inside any shapely geometry."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if g.geom_type == "LineString"]


def _joined(pieces: list) -> list:
    """Pieces of line joined end to end where they touch."""
    from shapely.geometry import MultiLineString
    from shapely.ops import linemerge, unary_union

    parts = _line_parts(unary_union(pieces)) if pieces else []
    return _line_parts(linemerge(MultiLineString(parts))) if len(parts) > 1 else parts


def osm_matches(lines: list, elements: list[dict]) -> tuple[dict, float]:
    """The OpenStreetMap rivers that follow one rough Natural Earth line.

    ``lines`` is the rough line as [lat, lon] points. Returns ``(rivers, coverage)``. ``rivers`` maps
    each matching OpenStreetMap river (its relation, or its name when it has none) to its name and
    its pieces near the rough line, in metres. Coverage is the detailed length divided by the rough
    length; near or above 1 means the whole line was found.
    """
    from pyproj import Transformer
    from shapely.geometry import LineString, MultiLineString

    to_metres = Transformer.from_crs("EPSG:4326", OSM_METRIC_CRS, always_xy=True)

    def project(lonlat: list) -> LineString:
        xs, ys = to_metres.transform([q[0] for q in lonlat], [q[1] for q in lonlat])
        return LineString(list(zip(xs, ys)))

    guide = MultiLineString([project([(lon, lat) for lat, lon in line]) for line in lines if len(line) > 1])
    near, far = guide.buffer(OSM_SAME_RIVER_RADIUS_M), guide.buffer(OSM_SEARCH_RADIUS_M)

    # Which river relation does each way belong to?
    relation_of: dict[int, int] = {}
    relation_name: dict[int, str] = {}
    for element in elements:
        if element["type"] == "relation" and element.get("tags", {}).get("waterway") == "river":
            relation_name[element["id"]] = element["tags"].get("name", "")
            for member in element.get("members", []):
                if member["type"] == "way":
                    relation_of.setdefault(member["ref"], element["id"])

    groups: dict[tuple, dict] = {}
    for element in elements:
        if element["type"] != "way" or len(element.get("geometry", [])) < 2:
            continue
        tags = element.get("tags", {})
        if element["id"] in relation_of:
            key = ("relation", relation_of[element["id"]])
            name = relation_name[relation_of[element["id"]]]
        elif tags.get("waterway") == "river" and tags.get("name"):
            key, name = ("name", tags["name"]), tags["name"]
        else:
            continue  # unnamed bits, and canals that are not part of a river relation
        way = project([(g["lon"], g["lat"]) for g in element["geometry"]])
        pieces = _line_parts(way.intersection(far))
        if not pieces:
            continue
        group = groups.setdefault(key, {"name": name, "shared": 0.0, "pieces": []})
        group["shared"] += way.intersection(near).length
        group["pieces"] += pieces

    # Stretches that carry a river's name without being in its relation belong to that river too.
    by_name = {group["name"]: key for key, group in groups.items() if key[0] == "relation" and group["name"]}
    for key in [k for k in groups if k[0] == "name" and k[1] in by_name]:
        loose = groups.pop(key)
        groups[by_name[key[1]]]["shared"] += loose["shared"]
        groups[by_name[key[1]]]["pieces"] += loose["pieces"]

    rivers = {key: group for key, group in groups.items() if group["shared"] >= OSM_MIN_SHARED_M}
    found = sum(part.length for part in _joined([piece for g in rivers.values() for piece in g["pieces"]]))
    return rivers, (found / guide.length if guide.length else 0.0)


def osm_rivers(code: str, listed: list[dict], cache_dir: Path) -> list[dict]:
    """Replace a country's rough river lines with the OpenStreetMap rivers that follow them.

    One rough line can turn out to be several real rivers (Natural Earth draws a main stem under one
    name), and one real river can be found through two rough lines. So the result lists the
    OpenStreetMap rivers themselves, each under its own name. A rough line along which OpenStreetMap
    has no river long enough to list is left out: such lines mostly cross lakes. A rough line is
    kept as it is only when OpenStreetMap could not be reached for it.
    """
    from pyproj import Transformer

    to_degrees = Transformer.from_crs(OSM_METRIC_CRS, "EPSG:4326", always_xy=True)
    result: list[dict] = []
    found: dict[tuple, dict] = {}
    matched: dict[str, set] = {}
    unreachable: set[str] = set()
    for river in listed:
        elements = fetch_osm(cache_dir, f"{code.lower()}-{river['id']}", river["lines"])
        if not elements:
            unreachable.add(river["id"])
        matches, coverage = osm_matches(river["lines"], elements)
        matched[river["id"]] = set(matches)
        names = ", ".join(sorted({g["name"] or "unnamed" for g in matches.values()})) or "nothing"
        print(f"{code}  {river['name']:<26} is, in OpenStreetMap: {names}  ({coverage:.0%} of the rough length)")
        for key, group in matches.items():
            entry = found.setdefault(key, {"name": group["name"] or river["name"], "pieces": [], "listed_as": set()})
            entry["pieces"] += group["pieces"]
            entry["listed_as"].add(river["name"])

    used: set = set()
    for key, entry in found.items():
        parts = [part.simplify(OSM_SIMPLIFY_M) for part in _joined(entry["pieces"]) if part.length >= OSM_MIN_PIECE_M]
        km = sum(part.length for part in parts) / 1000
        if km < OSM_MIN_LISTED_KM:
            print(f"{code}  {entry['name']:<26} left out: only {km:.0f} km of it follows a listed river")
            continue
        used.add(key)
        course = []
        for part in parts:
            xs, ys = part.coords.xy
            lon, lat = to_degrees.transform(list(xs), list(ys))
            course.append([[round(a, OSM_COORD_DECIMALS), round(b, OSM_COORD_DECIMALS)] for a, b in zip(lat, lon)])
        name = DISPLAY_NAMES.get(entry["name"], entry["name"])
        result.append({
            "id": slug(name), "name": name, "source_names": sorted(entry["listed_as"]), "lines": course,
            "bounds": bounds_of(course), "course": "OpenStreetMap", "_km": km,
        })

    for river in listed:
        if river["id"] in unreachable:
            print(f"{code}  {river['name']:<26} kept as a rough line: no answer from OpenStreetMap")
            result.append({**river, "course": "Natural Earth"})
        elif not matched[river["id"]] & used:
            print(f"{code}  {river['name']:<26} left out: OpenStreetMap has no river of "
                  f"{OSM_MIN_LISTED_KM} km or more along this line")

    result.sort(key=lambda r: -r["_km"])
    seen: dict[str, int] = {}
    for river in result:  # two rivers must never share an id
        seen[river["id"]] = seen.get(river["id"], 0) + 1
        if seen[river["id"]] > 1:
            river["id"] = f"{river['id']}-{seen[river['id']]}"
    return result


def build(source_dir: Path, use_osm: bool = True) -> dict:
    countries_src = load(source_dir, COUNTRY_FILE)
    raw_parts: dict[str, list] = {}
    for feature in countries_src["features"]:
        admin = feature["properties"]["ADMIN"]
        for code, name in COUNTRIES.items():
            if admin != name:
                continue
            parts = polygon_parts(feature["geometry"])
            if code == "NO":
                parts = [
                    p
                    for p in parts
                    if NORWAY_MAINLAND_MIN_LAT < min(c[1] for c in p[0])
                    and max(c[1] for c in p[0]) < NORWAY_MAINLAND_MAX_LAT
                    and min(c[0] for c in p[0]) > NORWAY_MAINLAND_MIN_LON
                ]
            raw_parts[code] = parts

    countries = {}
    for code, parts in raw_parts.items():
        polygons = [[to_latlon(ring) for ring in part] for part in parts]
        countries[code] = {
            "name": COUNTRIES[code],
            "polygons": polygons,
            "bounds": bounds_of([ring for polygon in polygons for ring in polygon]),
        }

    array_parts = {
        code: [[np.asarray([c[:2] for c in ring], dtype=float) for ring in part] for part in parts]
        for code, parts in raw_parts.items()
    }

    collected: dict[str, dict[str, dict]] = {code: {} for code in COUNTRIES}
    for river_file in RIVER_FILES:
        for feature in load(source_dir, river_file)["features"]:
            geometry = feature["geometry"]
            source_name = (feature["properties"].get("name") or "").strip()
            if not geometry or not source_name:
                continue
            name = DISPLAY_NAMES.get(source_name, source_name)
            lines = geometry["coordinates"] if geometry["type"] == "MultiLineString" else [geometry["coordinates"]]
            for line in lines:
                xy = np.asarray([c[:2] for c in line], dtype=float)
                if len(xy) < 2:
                    continue
                for code, parts in array_parts.items():
                    inside = points_in_country(xy[:, 0], xy[:, 1], parts)
                    if not inside.any():
                        continue
                    entry = collected[code].setdefault(
                        name, {"vertices_inside": 0, "lines": [], "source_names": set(), "km": 0.0}
                    )
                    entry["vertices_inside"] += int(inside.sum())
                    entry["source_names"].add(source_name)
                    for a, b in kept_runs(inside):
                        if b - a >= 2:
                            entry["lines"].append(to_latlon(line[a:b]))
                            entry["km"] += length_km(line[a:b])

    rivers = {}
    for code, by_name in collected.items():
        listed = [
            {
                "id": slug(name),
                "name": name,
                "source_names": sorted(entry["source_names"]),
                "lines": entry["lines"],
                "bounds": bounds_of(entry["lines"]),
                "_km": entry["km"],
            }
            for name, entry in by_name.items()
            if entry["vertices_inside"] >= MIN_VERTICES_INSIDE and entry["lines"]
        ]
        listed.sort(key=lambda r: -r["_km"])
        if use_osm:
            listed = osm_rivers(code, listed, source_dir / "osm")
        for river in listed:
            km = river.pop("_km")
            river.setdefault("course", "Natural Earth")
            print(f"{code}  {river['name']:<28} ~{km:5.0f} km  course from {river['course']:<13}  "
                  f"Natural Earth name(s): {river['source_names']}")
        rivers[code] = listed

    return {
        "source": (
            "Country outlines and the choice of rivers: Natural Earth 1:10m (public domain). "
            "River courses marked OpenStreetMap: © OpenStreetMap contributors, Open Database License."
        ),
        "note": "Display geometry. Not a catchment boundary or a measurement.",
        "countries": countries,
        "rivers": rivers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build web/data/geodata.json for the RivaScope map.")
    parser.add_argument("--source-dir", type=Path, help="Folder holding (or receiving) the downloaded source files")
    parser.add_argument("--no-osm", action="store_true", help="Keep the rough Natural Earth river lines")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = args.source_dir or Path(tmp)
        source_dir.mkdir(parents=True, exist_ok=True)
        data = build(source_dir, use_osm=not args.no_osm)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
