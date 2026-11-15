# RivaScope interface

The current logo is the team's hand-made artwork, copied unchanged. SI-assisted code use is described in the **Data** dialog and [SI disclosure](../../docs/si-disclosure.md), with metadata at `/si-use.json` and in API/export results. Provider data are not SI-generated observations.

The map-first front end of the team's trend backend. Flow: loading screen, occupation menu (first start only; the choice is saved and can be changed in the top bar), Europe map (Norway and Switzerland lit), country, river. It reads saved outputs only; opening or refreshing the page never downloads observations or runs a scientific build.

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

Each source is reported as ready, not built or unreadable from the files actually present. A source that is not built shows the backend command that builds it; follow the [trend guide](../trend/README.md) for credentials and prerequisites. **Data → Reload saved results** re-reads the files after a build. No imaginary records substitute for missing products, stations, variables or model comparisons.

## Screens

- **Country.** The left box lists the saved gauged rivers; the results box compares them (trend and window-change heatmaps, trend against catchment attribute, attribution, selection) and shows the station network (station/month, station/year, driver changes) when that build includes the country.
- **River.** The left box holds the reference and water-availability variables (up to four, drawn on one graph with one colour-coded axis per variable), the assessments and the calculation step (monthly average or daily). A ticked variable with no saved value in the chosen year stays in the legend as "no data" and is named under the graph. Every ticked assessment adds its figures under the graph:
  - *Risk assessment*: the saved Sen's slope and Mann-Kendall result for annual volume, half-volume date and daily-flow CV, a table of the saved indicators the chosen occupation reads first (`OCCUPATIONS` in `web/js/main.js`; these lists need review by the risk-assessment owner), and the flow surface. **Open water-flow assessment** opens Nikola's experimental historical diagnostics and optional user-supplied threshold scenario for saved Swiss/Norwegian observations. GLDAS is rejected for this assessment rather than silently substituted with observations.
  - *Statistics*: annual metric with trend, 10-year window means.
  - *Seasonal regime*: year against history, regime by window, daily flow of all years.
  - *Drivers*: driver correlations, flow against driver.
- **Timeline.** Under the map; drag or use the arrow keys to pick a saved hydrological year. The forecast slot is shown as unavailable: no forecast model is connected.
- Every figure has **Rescale** (fit all axes to the displayed data in their original units), **Table** (the saved records behind it, paged), **CSV** (all of those records) and **Full** (full screen; Esc closes). Rescale does not normalize different physical units. **Expand** hides the map; the divider between map and results can be dragged. **Close** hides the results panel while retaining the selected river and timeline; **Results** on the map reopens it.

Figures and numbers come from the existing backend (`mountain_water.trend.plots`, `stations` and the saved tables). Reference periods, hydrological/calendar years, units, missing values and significance conventions are kept from it; associations do not establish causation. The interface changes only typography and line colours of the backend figures. Not shown: the backend's trend map (it needs a base-map file from an external server, and the satellite map already shows the gauges) and the observed-against-GLDAS comparison figures (removed at the owner's request; a saved GLDAS build can still be opened as a source).

The **flow surface** is the grid of the backend's daily heatmap drawn in 3D: day of the hydrological year × year × saved daily discharge, with the year chosen on the timeline highlighted. Nothing is smoothed or estimated.

**No imaginary values.** The interface holds no synthetic, demonstration, random or hard-coded data. One kind of non-recorded number exists in the saved results themselves: the trend section interpolates discharge gaps of up to 5 days before computing its yearly statistics and flags those days (`discharge_vol_filled`). The four graphs of daily records (time series, flow surface, year against history, daily flow of all years) leave those days out and say how many; the record tables keep them with their flag. The saved yearly metrics, trends, regimes and window comparisons were computed by the trend section with those days included; changing that is a backend build setting (`max_gap_fill_days`).

The map shows gauge points and cached OpenStreetMap river segments where a conservative match exists. A missing course remains a point. Course geometry is display context, not a delineated upstream network or a calculation boundary. See [map sources and limits](map_component/README.md).

## Not implemented

Validated operational requirements, risk probabilities and forecasts are not implemented, and none are invented. An optional threshold is a user-supplied historical scenario, not a researched demand estimate. The experimental assessment's hardcoded screening rules are explicitly uncalibrated; changing occupation clears the scenario threshold. Scientific and operational interpretation require human review.

## Look

One typeface (DIN; Bahnschrift on Windows, DIN Alternate on macOS, Arial elsewhere), black instrument panels, a white results plate, one signal colour (international orange) for selection and the chosen year. Squares and 1px rules; no shadows, rounded corners, icons or third-party branding. Headings, numbers and paddings inside a box follow that box's width, so dragging the divider or expanding rescales them. The design tokens are at the top of `web/styles.css`; series colours are in `SERIES` in `web/js/main.js`.

## Files and API

| File | Responsibility |
| --- | --- |
| app.py, __main__.py, RivaScope.cmd | Local launcher |
| server.py | Static files and read-only JSON routes |
| backend.py | Saved-result catalogue, allowlisted backend figures/tables, refresh |
| river_geometry.py | Cached course lookup with match validation and attribution |
| risk_view.py | Read-only adapter for experimental historical-flow assessment |
| prediction_view.py | Unfinished placeholder |
| web/index.html, styles.css, js/ | Screens, map, figures and table presentation |
| web/vendor/leaflet/ | Leaflet 1.9.4 and licence |
| web/data/ | Display geometry with attribution |
| map_component/ | Reproducible geometry tools and provenance |

`GET /api/catalog` lists datasets, available options and views. `GET /api/figure` and `/api/table` accept allowlisted selection parameters. `GET /api/courses?dataset=ch` returns verified course segments and unmatched explanations. `GET /api/risk` reads observed discharge for a gauge, selected season, analysis/baseline years and optional threshold. `POST /api/refresh` clears saved-result caches. `/vendor/plotly.min.js` serves the runtime from the installed Plotly package, keeping it compatible with the Python figures. No CDN or frontend build is required for charts. Map background tiles need internet; saved figures and cached geometry do not.

Earlier interfaces remain preserved: the first web UI on archive/ui-handoff-20261115 and the industrial redesign on feature/industrial-results-ui.
