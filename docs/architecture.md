# Architecture

The repository contains one application. `ExecuteProgram.py` starts Streamlit with the current Python interpreter; `streamlit_app.py` delegates to `mountain_water.ui.app.main`. Neither launcher owns scientific calculations.

```text
ExecuteProgram.py -> streamlit_app.py -> ui/app.py
                                         |
                                  AssessmentRequest
                                         |
                                services/assessment.py
                                  /       |        \
                         data providers  analysis  models
                                  \       |        /
                                  AssessmentResult
                                    /          \
                              visualization   services/export.py
```

## Module boundaries

| Path | Responsibility | Boundary |
| --- | --- | --- |
| `contracts.py` | Typed outlets, interval series, provenance, requests and results | Validates units, timestamps, non-overlap and required metadata |
| `config.py`, `config/` | Local settings and verified outlet/catchment catalogue | Credentials stay in environment or ignored local configuration |
| `data/nve.py` | HydAPI daily mean discharge | Requires caller-owned key; preserves raw values and quality codes |
| `data/swiss.py`, `data/archive.py` | Pinned CAMELS-CH observed station archive | Historical coverage only; bounded ZIP member retrieval or local archive |
| `data/nasa.py`, `data/quality.py` | MODIS catchment index and versioned screening | Authorized Earth Engine retrieval; explicit area coverage and date-label caveats |
| `data/csv_import.py` | User-supplied flow, driver and requirement data | Requires matching metadata and validated shared contracts |
| `data/demo.py` | Opt-in synthetic developer demonstration | Separate identity and explicit synthetic provenance |
| `analysis/` | Baselines, interval integration, threshold exposure, period metrics and trends | Pure calculations; no provider calls or Streamlit dependencies |
| `models/` | Seasonal baseline, team-model extension point and hindcasts | Training ends by issue date; outputs retain native monthly intervals |
| `services/assessment.py` | Fetches needed windows and coordinates calculations | UI receives one result with independent provider states |
| `services/cache.py` | Local JSON caching | Identity includes scientific inputs; no credential-based identity or serialized executable objects |
| `services/export.py` | Portable evidence ZIP | Exports results and provenance, never settings or credentials |
| `visualization/` | Plotly figures and interpretation metadata | Receives results; does not retrieve or recompute source data |
| `ui/app.py` | Controls, status rendering, maps, tabs and download action | Shows results from the last submitted request |

## Assessment lifecycle

1. Load the two verified outlet records and WGS84 upstream geometries. No time-series provider request occurs during initial page load.
2. Submit analysis dates, reference years, season, water-year start, requirement, model and optional NASA variable. Dates in controls are inclusive; internal intervals are half-open.
3. Retrieve flow over the union of analysis and reference windows. Retrieve the NASA variable over the analysis window independently. Explicit imports use the same downstream contracts.
4. Calculate observed coverage and volume, calendar baseline, complete-period metrics, threshold exposure, descriptive trends and the outlook where inputs permit.
5. Render independent flow/NASA states, interpretation limits and last-submitted settings. Export the complete evidence bundle on request.

## Provider states and caching

`ready`, `authentication_required`, `pending`, `unsupported`, `no_data` and `error` are distinct states. A retryable quota response is different from an unsupported date range or an empty valid query. A provider failure carries no fabricated observations. Successful NASA context can still be displayed when flow is unavailable, and vice versa.

Caches use hashed identities including relevant station, geometry, dates, product/version, aggregation, calendar and quality policy. Retrieval timestamps and fresh/cached/imported origins remain part of the evidence. NVE requests are chunked; NASA requests are limited to ten years and processed in bounded date chunks. The pinned Swiss station archive is cached separately from a selected analysis window. Local caches and downloaded archives are ignored by Git.

## Six coordinated workstreams

| Workstream | Main integration surface |
| --- | --- |
| Data and provenance | `data/`, `config/`, source ledger |
| Historical hydrology | `analysis/flow_metrics.py`, `baseline.py` |
| Requirements and exposure | `analysis/risk.py`, `RequirementSeries` |
| Models and validation | `models/`, `ForecastResult` |
| Visualization and interface | `visualization/`, `ui/` |
| Integration, quality and delivery | Shared contracts, services, tests, documentation and CI |

These are ownership boundaries within one application, not separate apps or permanent branch assignments. Record a human owner before beginning a task. Coordinate changes to shared contracts and use separate worktrees for simultaneous writers. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) for branches and pull requests.

## Extension rules

A new provider must return the existing result states and retain original units, quality, calendar, provenance and missingness. A new outlet requires a verified station-to-upstream-polygon join. A new model must define its inputs, forecast intervals, future-driver assumptions and validation protocol before the interface treats it as available. Add a view to the existing application rather than creating another entry point.
