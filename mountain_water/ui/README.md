# RivaScope interface

The screens of RivaScope: loading screen, occupation menu, map, and the river
view with one shared graph, the risk assessment, statistics and physical
models.

It is a plain web page (HTML, CSS, JavaScript, no framework and no build
step) served by a small Python server from the standard library. It does not
use Streamlit or any hosted service, and nothing in it shows another
product's branding.

## Start it

From the repository root, in the project's Python environment:

```text
python -m mountain_water.ui
```

RivaScope opens in its own window (Chrome or Edge without address bar; a
normal browser tab if neither is installed). Closing the window stops the
server. On Windows you can also double-click `RivaScope.cmd` in this folder.

| Option | What it does |
| --- | --- |
| `--browser` | open a normal browser tab instead of the app window |
| `--no-window` | only start the server and print its address |
| `--port 8765` | choose the port (a nearby free one is used if it is taken) |

The map needs an internet connection for its satellite imagery. The small
credits on the map (Esri imagery, OpenStreetMap river courses) are required by
those sources.

## Where the numbers come from

- **Measured rivers** come from the trend section (`mountain_water/trend`).
  The interface reads its saved tables and calls its functions; it never
  changes anything there. Prepare the data once with
  `python -m mountain_water.trend download` and
  `python -m mountain_water.trend build`. Without it the app still runs, on
  imaginary data only, and says so under "About the data".
- **Imaginary data** fills everything that has no real source yet, and is
  marked "imaginary" wherever it appears (dotted lines in the graph):
  - rivers without measurements: all of Norway and the large Swiss rivers;
  - evaporation;
  - the prediction for the year after the latest data;
  - the physical model;
  - every occupation's requirement, and the risk index and its scores.

  All of it is made in `imaginary.py`. To retire one of them, replace the
  call to `imaginary` in the file listed below.

## Files

| File | What it holds |
| --- | --- |
| `app.py`, `__main__.py` | starts the server and opens the window |
| `server.py` | hands out the pages in `web/` and answers their requests as JSON |
| `state.py` | the selection sent with each request (river, year, variables, ...) |
| `controls.py` | what can be chosen: occupations with their requirement scenarios, variables, assessments, calculation methods |
| `overview.py` | countries, rivers and data status for the menus and the map |
| `data_source.py` | the bridge to the trend section, and the imaginary record for rivers without measurements |
| `trend_view.py` | the shared graph and the statistics table |
| `risk_view.py` | the occupation's risk assessment: flow against the requirement, long-term changes, volatility plane |
| `prediction_view.py` | the prediction year and the physical-model section (imaginary for now) |
| `imaginary.py` | all imaginary data |
| `wording.py` | numbers as short plain text |
| `web/index.html`, `web/styles.css` | the page and its look |
| `web/js/main.js` | what is on screen and what happens on a click |
| `web/js/chart.js` | the graph (hand-drawn SVG) and the year bars |
| `web/js/plane.js` | the volatility plane |
| `web/js/map.js` | the satellite map |
| `web/vendor/leaflet/` | the Leaflet map library with its licence |
| `web/data/geodata.json` | country outlines and the courses of the large rivers (see `map_component/`) |
| `map_component/` | the tool that builds `geodata.json`, and the map's sources, licences and limits |

## Things to know

- The risk comparison in `risk_view.py` (days below the requirement,
  shortfall periods, missing volume) is a stand-in. It belongs to
  `mountain_water/risk_assessment`, which is still empty, and should move
  there.
- Occupation questions and "still needed" lists for hydropower, data centres
  and government follow the project guide. Power plant and defence are not
  specified there; their wording in `controls.py` is a proposal.
- The year slider uses calendar years. The statistics use the trend
  section's hydrological years (October to September); the table says so.
- A missing value is shown as a gap and never as zero.
- To add a variable, add it to `VARIABLES` in `controls.py` with the column
  of the daily table that holds it. To add an occupation, add it to
  `OCCUPATIONS`.
