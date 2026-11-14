# Mountain Water Availability

One Python/Streamlit application for measured mountain-catchment discharge, seasonal change and exposure to a user-defined water requirement. Implements **Codex_Project_Handoff (3).pdf** for the Oslo NASA Space Apps 2026 team.

The catalogue includes NVE Atnasjø (2.32.0), Norway, and FOEN Chamuerabach at La Punt-Chamues-ch (2263), Switzerland, with matched upstream polygons. Norway requires an NVE HydAPI key. Switzerland uses measured CAMELS-CH v0.9 archive observations (1981–2020). NASA MODIS snow-index context requires authenticated Earth Engine access. There is no synthetic fallback.

## Run
Use Python 3.11 in a virtual environment; see [SETUP.md](SETUP.md).

```text
python -m pip install -c constraints.txt -e ".[dev]"
python ExecuteProgram.py
```

Select a catchment and run an assessment. The labelled developer demo works offline. For measured data, choose Switzerland, 2011–2020 and reference years 2001–2010. NASA access is configured independently.

## Features
- Quality-aware volume, complete seasonal/year summaries and half-volume timing.
- Calendar-day reference distributions, separate from scenario requirements.
- Time-weighted interval-average deficits, margins and gap-censored events.
- Quantity, timing and residual-variability axes, with a 2D alternative.
- Catchment-weighted NASA snow-index context and valid-area coverage.
- A 12-month seasonal-climatology outlook with chronological hindcasts.
- CSV/JSON evidence export with sources, assumptions and access states.

Results are exploratory. Observed flow includes historical management; scenario shortfall does not establish service failure. Monthly forecasts cannot establish daily events. Historical quantiles are not prediction intervals. The custom team equation remains unavailable until supplied.

## Development
Main is the shared foundation; small branches and PRs target main. See [CONTRIBUTING.md](CONTRIBUTING.md), [architecture](docs/architecture.md), [contracts](docs/data-contracts.md), [methods](docs/methods.md), [tasks](docs/task-checklist.md), [demo](docs/demo-guide.md) and [validation](docs/validation.md).

```text
python -m ruff check .
python -m pytest
```

Software is MIT licensed; data retain their own terms in the [source ledger](docs/source-ledger.md). No database or deployment is required.
