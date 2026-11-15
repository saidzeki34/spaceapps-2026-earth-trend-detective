# River-flow assessment implementation

2026-11-15: user-authorized implementation assisted by Perplexity.
Branch: risk-assessment/risk-assessment-implementation; main is not modified.

## Scope and methods

The existing sidebar risk placeholder becomes a button opening a native dialog.
The local server injects /js/risk.js into its HTML response and exposes GET /api/risk.
The original main.js and map are untouched; no catchment map is introduced.
Legacy About/catalogue text still describes the earlier unfinished risk module.
This document and the new popup describe the experimental implementation.

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

Use a clean checkout or separate worktree. Do not overwrite teammate changes.
From the existing repository root, first inspect git status --short. If it lists
uncommitted work, preserve that work before proceeding. Then run:

```sh
git fetch origin
git switch --track origin/risk-assessment/risk-assessment-implementation
python -m pip install -e ".[dev]"
python -m pytest tests/risk_assessment -q
python -m pytest
python -m mountain_water.ui --browser
```

If the local branch already exists, use git switch
risk-assessment/risk-assessment-implementation, then git pull --ff-only.
A fresh worktree does not inherit ignored data. Copy your existing saved processed
datasets into its data/processed directory or follow the trend build guide using
your cached inputs. Never commit the datasets.

Choose an occupation, Switzerland or Norway, an observed dataset and a river.
Under Assessments, click Open water-flow risk assessment. Confirm the gauge, choose
analysis and baseline years within coverage, and calculate. Rotate the 3D point,
switch to 2D, inspect volume/timing/flow plots, add a threshold, inspect episodes
and export JSON. Test an empty baseline, short record and model dataset: these
must show unavailable/partial states rather than invented coordinates. Close with
Escape and reopen. Confirm original navigation and saved-result plots still work.

## Checks and attribution

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
