"""Build the small map geometry file used by the RivaScope map.

This is a one-off developer tool, not part of the running application.
It reads public-domain Natural Earth 1:10m vector data and writes
``frontend/geodata.json`` with:

* the outlines of the countries the map lights up (Norway, Switzerland);
* the named river centre lines that fall inside each of those countries.

The geometry is for display and selection only. It is cartographically
generalized and must not be used as a catchment boundary, a river length
or any other measurement. River names are taken from Natural Earth and
still need a review by the team against national sources.

Usage (from the repository root)::

    python mountain_water/ui/map_component/build_geodata.py [--source-dir DIR]

Without ``--source-dir`` the three source files are downloaded from the
Natural Earth GitHub mirror into a temporary folder.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np

SOURCE_BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
COUNTRY_FILE = "ne_10m_admin_0_countries.geojson"
RIVER_FILES = ("ne_10m_rivers_lake_centerlines.geojson", "ne_10m_rivers_europe.geojson")
OUTPUT = Path(__file__).parent / "frontend" / "geodata.json"

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

# Natural Earth name -> name shown in RivaScope. Only spelling variants
# and local names of the same river are merged here.
DISPLAY_NAMES = {
    "Tana River": "Tana",
    "Rhein": "Rhine",
    "Rhin": "Rhine",
    "Rhne": "Rhône",
    "Klarlven": "Trysilelva (Klarälven)",
    "Klarälven": "Trysilelva (Klarälven)",
    "Patsoyoki": "Pasvikelva",
}

COORD_DECIMALS = 4


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


def build(source_dir: Path) -> dict:
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
        for river in listed:
            km = river.pop("_km")
            print(f"{code}  {river['name']:<28} drawn ~{km:6.0f} km  from {river['source_names']}")
        rivers[code] = listed

    return {
        "source": "Natural Earth 1:10m (public domain), naturalearthdata.com",
        "note": "Generalized display geometry. Not a catchment boundary or a measurement.",
        "countries": countries,
        "rivers": rivers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frontend/geodata.json from Natural Earth data.")
    parser.add_argument("--source-dir", type=Path, help="Folder holding (or receiving) the Natural Earth GeoJSON files")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = args.source_dir or Path(tmp)
        source_dir.mkdir(parents=True, exist_ok=True)
        data = build(source_dir)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
