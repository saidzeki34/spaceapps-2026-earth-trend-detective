# RivaScope interface

A local results browser for the team's trend backend. One font family, compact controls, square panels, backend Plotly figures and inspectable tables. It reads saved outputs; opening or refreshing the page never downloads observations or runs a scientific build.

## Start

```text
python -m pip install -e ".[dev]"
python -m mountain_water.ui
```

The launcher opens a Chrome/Edge app window, or a browser tab when no app-window browser exists. Closing that window stops its server. `--no-window` runs only the server; `--browser` opens a normal browser tab; `--port 8765` chooses a port (a nearby free port is used when occupied). Windows also has `RivaScope.cmd`.

## Saved results

| Source | Default saved directory | Meaning |
| --- | --- | --- |
| Swiss observations | data/processed/trend | CAMELS-CH catchment results |
| Norwegian observations | data/processed/trend_no | NVE discharge with seNorge drivers |
| Swiss GLDAS | data/processed/trend_gldas | Modelled environmental/runoff context |
| Norwegian GLDAS | data/processed/trend_no_gldas | Modelled environmental/runoff context |
| Station network | data/processed/trend_stations | Countries/stations actually included in that saved build |

The source menu reports ready, missing or error from the files actually present. Missing sources show the corresponding backend command; follow the [trend guide](../trend/README.md) for credentials and prerequisites. Click **Reload saved results** after a build. No imaginary records substitute for missing products, stations, variables or model comparisons.

Catchment views include time series, historical hydrographs, seasonal regimes, annual metrics, daily heatmaps, window means, correlations and driver scatters. Regional views expose trend/window-change heatmaps, maps, attribute comparisons, attribution and selection. Station views expose month/year heatmaps and driver changes. Source comparisons require both observed and GLDAS outputs and retain their model/observation distinction. Tables and figures come from the existing backend. Reference periods, hydrological/calendar years, units, missing values and significance conventions are retained from it; associations do not establish causation.

The map shows gauge points and actual cached OpenStreetMap river segments where a conservative match exists. A missing course remains a point, with an explanation. Course geometry is display context, not a delineated upstream network or a calculation boundary. See [map sources and limits](map_component/README.md).

## Incomplete sections

Risk assessment, occupational requirements, forecasts and the team's physics model are not implemented. Their former fabricated values have been removed from the active UI. The optional **volatility surface demonstration** is explicitly synthetic, with arbitrary axes/values; it illustrates 3D interaction and does not use a station's results or estimate risk.

## Files and API

| File | Responsibility |
| --- | --- |
| app.py, __main__.py, RivaScope.cmd | Local launcher |
| server.py | Static files and read-only JSON routes |
| backend.py | Saved-result catalogue, allowlisted backend figures/tables, refresh |
| river_geometry.py | Cached course lookup with match validation and attribution |
| risk_view.py, prediction_view.py | Explicitly unfinished placeholders |
| web/index.html, styles.css, js/ | Controls, map, figures and table presentation |
| web/vendor/leaflet/ | Leaflet 1.9.4 and licence |
| web/data/ | Display geometry with attribution |
| map_component/ | Reproducible geometry tools and provenance |

`GET /api/catalog` lists datasets, available options and views. `GET /api/figure` and `/api/table` accept allowlisted selection parameters. `GET /api/courses?dataset=ch` returns verified course segments and unmatched explanations. `POST /api/refresh` clears saved-result caches. `/vendor/plotly.min.js` serves the runtime from the installed Plotly package, keeping it compatible with the Python figures. No CDN or frontend build is required for charts. Map background tiles need internet; saved figures and cached geometry do not.

Old bootstrap/rivers/outlines/view routes and their synthetic data generators have been retired. The original UI remains preserved on archive/ui-handoff-20261115.
