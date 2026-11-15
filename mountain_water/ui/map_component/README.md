# RivaScope map: sources and limits

The map itself is drawn by `mountain_water/ui/web/js/map.js` with the Leaflet
library kept in `mountain_water/ui/web/vendor/leaflet/`. This folder holds the
tool that prepares the map's outlines and river courses, and the notes on
where the map's content comes from. See `mountain_water/ui/README.md` for the
interface as a whole.

## What the map does

- Shows satellite imagery of Europe with country borders and place names.
- Shades everything except the countries that can be explored (Norway and
  Switzerland for now).
- After a country is chosen, zooms in and draws its rivers. A river can be
  chosen on the map or in the left box.
- Large rivers are drawn as lines along their mapped course. Gauged rivers
  use verified OpenStreetMap waterway segments where available, with a dot
  at the measuring point. Missing courses stay as station points with an
  unavailable explanation. Catchment polygons are not river courses.

## External sources used

| What | Source | Notes |
| --- | --- | --- |
| Satellite imagery tiles | Esri World Imagery (`server.arcgisonline.com`) | Loaded live by the browser, so the map needs an internet connection. The credit shown on the map is required by Esri. Esri's terms of use have not been reviewed by the team yet. |
| Borders and place names | Esri World Boundaries and Places reference tiles | Same as above. |
| Country outlines, and which large rivers are listed | Natural Earth 1:10m, public domain (naturalearthdata.com), files `ne_10m_admin_0_countries`, `ne_10m_rivers_lake_centerlines`, `ne_10m_rivers_europe` | Stored in `web/data/geodata.json`, produced by `build_geodata.py`. |
| Courses and names of the large rivers | OpenStreetMap, © OpenStreetMap contributors, Open Database License (ODbL) | Fetched once by `build_geodata.py` through the public Overpass service and stored in `web/data/geodata.json`. The credit "rivers © OpenStreetMap contributors" on the map is required. Because the file holds data derived from OpenStreetMap, it may be shared only under the ODbL. |
| Gauged-river segments | OpenStreetMap, Open Database License (ODbL) | `web/data/gauge_courses.geojson` stores the original source vertices, way IDs, source timestamps and matching information. Attribution: © OpenStreetMap contributors. Source-backed segments may cover only part of a river. |
| Measuring points | Saved trend backend station attributes | Coordinates retain their source identity. A station point is not a complete river or catchment geometry. |
| Map library | Leaflet 1.9.4 (BSD-2-Clause) | Kept in `web/vendor/leaflet/` with its licence; no longer loaded from a CDN. |

These source notes, including vendored Leaflet, OpenStreetMap river courses
and CAMELS-CH display catchments, are recorded in `docs/source-ledger.md` by
the submitted-handoff integration. The review limits below still apply.

## How the large rivers are chosen and drawn

1. Natural Earth lists a river for a country when at least 20 points of its
   line fall inside the country outline. That is this tool's working
   definition of a large river, not a hydrological one.
2. Natural Earth's line is too rough for satellite imagery: it can sit a
   kilometre beside the real river. So the tool looks up the OpenStreetMap
   rivers that run along each rough line (at least 8 km of the river within
   1.2 km of the line) and uses their detailed course instead, cut to the
   stretch that the rough line covers.
3. One rough line can be several real rivers. Natural Earth's "Vorma", for
   example, is Gudbrandsdalslågen, Vorma and the lower Glomma under one name.
   The rivers are therefore listed as OpenStreetMap knows them, each under its
   own name. A river is listed when at least 25 km of it follows a rough line.
4. A rough line along which OpenStreetMap has no such river is left out. Such
   lines mostly cross lakes: Natural Earth's "Göta" in Norway, for example, is
   the middle of lake Femunden. A rough line is kept as it is only when
   OpenStreetMap could not be reached for it.

Where a river runs through a lake, the line stops at the lake and continues
after it.

## Limits

`geodata.json` is for display and selection only.

- River courses are simplified to about 12 m for drawing. They are not
  catchment boundaries, river lengths or outlet positions.
- The list of rivers follows the rule above and has not been reviewed by a
  hydrologist; it should be checked against NVE and FOEN before a demo. The
  tool prints which OpenStreetMap rivers it found for each Natural Earth name.
- Norway's outline leaves out Svalbard, Jan Mayen and Bouvet Island.
- Gauged-river segments are for display only and do not establish complete
  upstream coverage, a basin network or a validated hydrological match.

## Gauged mountain rivers

`build_gauge_courses.py` reads existing gauge metadata and cached OpenStreetMap
ways. Its optional `--fetch` switch makes one bounded query for river/stream
ways within 1.5 km of at most 40 gauges; it never requests observations. The
application itself makes no geometry downloads. Query results stay in an
ignored cache; only selected display segments are distributed.

Matching requires a normalized provider river name or its explicit alias,
a source segment within 150 m of the measuring point, and connected original
OpenStreetMap vertices. Conflicting nearby components are rejected. No line
is invented between disconnected pieces. The file records source way IDs,
OpenStreetMap base timestamps and retrieval timestamps where known; an
inherited cache without a retrieval timestamp is not given an invented date.

The bundled geometry is derived from OpenStreetMap and distributed under the
[Open Database License](https://opendatacommons.org/licenses/odbl/1-0/).
Keep visible [OpenStreetMap attribution](https://www.openstreetmap.org/copyright)
on maps. OpenStreetMap documents
[`waterway=river`](https://wiki.openstreetmap.org/wiki/Tag:waterway%3Driver)
as the linear river course. Its
[Overpass usage guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
supports caching bounded queries rather than using public servers as an
application backend.

To rebuild from a locally prepared JSON list of gauge dictionaries
(`id`, `country`, `river`, `name`, `lat`, `lon`):

```text
python mountain_water/ui/map_component/build_gauge_courses.py --gauges tmp/gauges.json --cache-dir tmp/gauge-course-cache --fetch
```

Omit `--fetch` to rebuild entirely from the cached responses. The runtime
reader also rechecks gauge identity, river name and coordinates before using
a stored course. Every unavailable course has a reason in the returned
GeoJSON collection's `missing` mapping.

## Rebuilding

From the repository root, in the project's Python environment:

```text
python mountain_water/ui/map_component/build_geodata.py --source-dir SOME_FOLDER
```

The tool downloads the three Natural Earth files and one OpenStreetMap answer
per river into that folder and reuses them on the next run. The public
OpenStreetMap service is slow and sometimes busy: expect about a minute per
river the first time. `--no-osm` skips that step and keeps the rough lines.
