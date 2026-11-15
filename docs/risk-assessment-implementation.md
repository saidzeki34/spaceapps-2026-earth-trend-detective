# River-flow assessment implementation

2026-11-15: user-authorized implementation assisted by Perplexity.
Original branch: risk-assessment/risk-assessment-implementation at 8c168c8.
The user subsequently authorized its integration with the selected UI. The separate
ui-fixes-continuation branch is excluded. Original contributor history is preserved.

## Scope and methods

The existing Risk assessment trend headline keeps its saved indicators and includes
an Open water-flow assessment button opening an optional native dialog.
The local server injects /js/risk.js into its HTML response and exposes GET /api/risk.
The dialog reuses the selected UI's existing dialog, results, typography and control
styles. No catchment map or alternate interface theme is introduced. These historical
diagnostics and explicit threshold scenarios remain experimental; a validated
operational risk model and prediction remain unfinished.

Only saved CAMELS-CH/NVE daily river discharge is accepted, not GLDAS runoff or
station-network summaries. Opening the popup downloads nothing and builds no saved
dataset. Diagnostics are computed in memory. Missing datasets retain the backend
status and build command. No occupation-derived requirements are invented.

X is Sen slope of seasonal volume as percent of a fixed baseline per decade.
Y is Sen slope of the whole hydrological year's half-volume day, days per decade.
Z is sample standard deviation of seasonal volume divided by baseline volume,
in percent. Raw variability includes the trend; it is not variability change.
SciPy theilslopes uses actual years. All XYZ coordinates use the same complete-year
intersection. Minimum 15 such years and 10 complete baseline seasons are prototype
quality rules, not guarantees. Defaults: HY 1982-2020, baseline HY 1982-2001, Aug-Sep.
Hydrological-year start comes from metadata with October as fallback.

Missing, negative, infinite and flagged interpolated flows are excluded. Expected
daily calendars include leap days; no scaling estimates missing seasonal volume.
Missing interpolation flags trigger a warning. Daily baseline percentile bands
require 10 valid values per calendar day, so February 29 may have no band.
Optional constant selected-season threshold is a historical scenario, not actual
unmet demand. Missing dates and season/analysis boundaries split and censor episodes.
Deficits integrate valid daily flow only. Complete durations and longest observed
segments are distinguished. Above-requirement volume does not establish flood risk.

Provider quality codes are not newly filtered. No significance claim, confidence
interval, attribution, forecast, usable-supply or management model is added. Small
positive baselines are not automatically rejected: inspect absolute baseline volume.
Zero-baseline normalized coordinates are unavailable. Multiple-gauge overlays,
custom schedules, detrended variability and resilience modelling remain future work.

## Local test instructions

Use a clean checkout or separate worktree containing the integrated code. Do not
overwrite teammate changes. From that checkout's root, using its environment, run:

```sh
python -m pytest tests/risk_assessment tests/test_ui_server.py -q
node tests/risk_assessment/risk-rules.test.mjs
python -m mountain_water.ui --browser
```

A fresh worktree does not inherit ignored data. Copy your existing saved processed
datasets into its data/processed directory or follow the trend build guide using
your cached inputs. Never commit the datasets.

Choose an occupation, Switzerland or Norway, an observed dataset and a river.
In the Risk assessment headline, click Open water-flow assessment. Confirm the gauge, choose
analysis and baseline years within coverage, and calculate. Rotate the 3D point,
switch to 2D, inspect volume/timing/flow plots, add a threshold, inspect episodes
and export JSON. Test an empty baseline, short record and model dataset: these
must show unavailable/partial states rather than invented coordinates. Close with
Escape and reopen. Confirm original navigation and saved-result plots still work.

## Checks and attribution

The 2026-11-15 integration resolved the adapter conflict without changing Nikola's
scientific calculations. It fixes the launcher's connection to the current headline
and reads the current `d` dataset hash key, so a selected GLDAS source cannot silently
fall back to observations. Changing the source or gauge clears the scenario threshold.
Null hydrological-year metadata uses the documented October fallback. Missing saved
data retains the build command; incompatible model/station sources are rejected.

The combined focused Python suite passed **38 tests in 24.97 seconds**, covering the
risk calculations, adapter, HTTP dispatch and existing server routes. Node screening,
selection and surface assertions and risk-module syntax passed. The JavaScript test
loads the browser module explicitly as ESM and works on the installed Node 18 without
experimental flags. These checks use synthetic fixtures; they do not validate methods
or findings. A separate read-only smoke check against the already saved local Swiss
gauge 2105 and Norwegian gauge 103.1.0 returned ready responses with 39 common complete
years each and no exposure calculation without a supplied threshold. No data was
downloaded or written. This confirms adapter compatibility, not scientific validity.
Browser checks are reported in the integration handoff rather than inferred here.

Browser checking exposed a close/reopen race: a queued native close event could
cancel the new request, and plot cleanup could run while Plotly was still drawing.
The integration serializes graph updates and cleanup, waits for every plot to
settle, ignores stale request/close events and reports readiness after drawing.
Stress assertions with delayed real Plotly calls cover rapid threshold changes,
close/reopen, 2D/3D switches and occupation changes during drawing. They preserve
the latest selection, clear the threshold on occupation changes, and hide/purge
old output on close without overlapping updates to the same graph.

Original branch validation record, preserved for attribution:

26 focused tests passed in an isolated Python sandbox using synthetic fixtures,
including calculations, missingness, baseline, thresholds, adapter and HTTP dispatch.
Node --check passed for risk.js. The repository-wide suite, real-data integration,
interactive browser rendering and the user's local environment remain untested.
Synthetic tests do not validate scientific findings or live providers.

Sources: user-supplied definitions and repository code/documentation inspected
through GitHub. Existing NumPy, pandas, SciPy and Plotly dependencies are reused;
pytest provides tests. No new data source, credentials, deployment, service or
dataset download was introduced. Perplexity prepared implementation and checks
on 2026-11-15. The team must review methods and competition attribution.
