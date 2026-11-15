# RivaScope map component

The interactive map of the RivaScope interface. `frontend/index.html` is a
small Leaflet page that Streamlit embeds; `mountain_water/ui/charts/maps.py`
is its Python side.

## What it does

- Shows satellite imagery of Europe with country borders and place labels.
- Shades everything except the countries that can be explored (Norway and
  Switzerland for now).
- After a country is chosen, zooms in and draws its rivers. A river can be
  chosen on the map or in the left box.
- Reports clicks to Python as `{"kind": "country" | "river" | "europe", "id", "seq"}`.

## External sources used

| What | Source | Notes |
| --- | --- | --- |
| Satellite imagery tiles | Esri World Imagery (`server.arcgisonline.com`) | Loaded live by the browser; attribution is shown on the map. Esri's terms of use apply and have not been reviewed by the team yet. |
| Borders and place labels | Esri World Boundaries and Places reference tiles | Same as above. |
| Country outlines and river lines | Natural Earth 1:10m, public domain (naturalearthdata.com), files `ne_10m_admin_0_countries`, `ne_10m_rivers_lake_centerlines`, `ne_10m_rivers_europe` | Stored in `frontend/geodata.json`, produced by `build_geodata.py`. |
| Map library | Leaflet 1.9.4 (BSD-2-Clause), loaded from unpkg.com | Needs an internet connection, as do the tiles. |

These sources still need an entry in `docs/source-ledger.md`. That file is
outside the UI section and was left untouched.

## Limits of the geometry

`geodata.json` is for display and selection only.

- The lines are cartographically simplified. They are not catchment
  boundaries, river lengths or outlet positions.
- A river is listed for a country when at least 20 of its Natural Earth
  vertices fall inside the country outline. That is this component's working
  definition of "significant", not a hydrological one.
- River names are Natural Earth's. A few were merged or renamed in
  `build_geodata.py` (`DISPLAY_NAMES`): Rhein/Rhin → Rhine, Tana River → Tana,
  Patsoyoki → Pasvikelva, Klarälven → Trysilelva (Klarälven). Several
  Norwegian names (for example Vorma, Lågen, Mane, Verkselv, Göta) look
  generalized or unusual and should be checked against NVE before a demo.
- Norway's outline leaves out Svalbard, Jan Mayen and Bouvet Island.

## Rebuilding the geometry

From the repository root, with NumPy available:

```text
python mountain_water/ui/map_component/build_geodata.py
```

The script downloads the three Natural Earth files into a temporary folder
(or reads them from `--source-dir`) and rewrites `frontend/geodata.json`.
