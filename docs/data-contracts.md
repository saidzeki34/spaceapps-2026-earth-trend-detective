# Data contracts and imports

`mountain_water/contracts.py` defines the common records. Internal time intervals are **half-open `[start, end)`**, with timezone-aware boundaries converted to UTC. Rows must be ordered, have unique starts and positive durations, and must not overlap. Gaps are allowed and remain gaps. An absent value is never interpreted as zero.

## Records

| Record | Required meaning |
| --- | --- |
| `Outlet` | Stable ID, country/provider station ID, location, matched upstream catchment ID/area/source, supported period, regulation status, calendar timezone and optional Polygon/MultiPolygon |
| `Provenance` | Provider, source URL, product/station identifier, version, timezone-aware retrieval date, license, attribution, units, data kind and transformations |
| `FlowSeries` | Outlet, interval table, provenance, `meaning="interval_average"` and origin |
| `DriverSeries` | Outlet ID, variable, interval table, provenance, spatial resolution, aggregation and origin |
| `RequirementSeries` | Interval threshold table, name, intended user, source, scenario/documented status, units, meaning and resilience |
| `AssessmentRequest` | Outlet, analysis dates, independent reference years, selected months, water-year start, variables, model and issue date |
| `ProviderResult` | Explicit status, explanation, optional data and optional retry interval |
| `ForecastResult` | Status, issue date, monthly table, model, training description, interval interpretation, assumptions and hindcasts |
| `AssessmentResult` | Request, independent provider results, observations, baseline, period metrics, exposure, trends, variability, forecast, requirement and limitations |

Provenance `kind` is one of `observed`, `modelled`, `forecast`, `synthetic` or `satellite_retrieval`. Unknown metadata must be identified explicitly, not guessed. A populated field is an audit trail, not proof that its scientific content has been independently verified.

## Flow CSV and JSON sidecar

The CSV requires `start`, `end`, `discharge_m3s`, `quality` and `valid`. `valid` must be `true` or `false`. Nonempty discharge values must be finite and nonnegative. Keep rejected original values and native quality codes in additional columns, while marking the scientific value missing and invalid. Units are exactly `m3/s`; convert other units explicitly and record the transformation.

The JSON sidecar requires:

```json
{
  "outlet_id": "camels-2263",
  "calendar_timezone": "UTC",
  "meaning": "interval_average",
  "provenance": {
    "provider": "REPLACE with actual provider",
    "source_url": "REPLACE with actual source URL",
    "identifier": "REPLACE with actual station/product identifier",
    "version": "REPLACE with source version or explicitly unknown",
    "retrieved_at": "2026-11-15T00:00:00+00:00",
    "license": "REPLACE with verified applicable terms",
    "attribution": "REPLACE with required attribution",
    "units": "m3/s",
    "kind": "observed",
    "transformations": ["REPLACE with actual parsing, units and quality policy"]
  }
}
```

This is a **schema example**, not evidence of a retrieval. Replace all example metadata, including the timestamp. The outlet ID and calendar timezone must match the selected catalogue outlet. Do not relabel another basin's observations to make an import pass.

Instantaneous samples are rejected. They first need a documented integration method and maximum-gap policy. Calendar baselines, annual timing and monthly forecasts additionally require full 24-hour means beginning at the selected outlet's calendar midnight; arbitrary subdaily intervals do not automatically satisfy that contract.

## Environmental driver import

The driver CSV requires `start`, `end`, `value` and `valid_area_fraction`. Coverage must lie in `[0, 1]`. Its sidecar contains `outlet_id`, `variable`, `spatial_resolution_m`, `aggregation` and the same `provenance` object. The outlet must match the assessment; document the exact upstream polygon, product, native grid, area weighting, quality screen and coverage threshold in provenance. An import is not automatically certified as a NASA product merely because it appears in the NASA tab.

The implemented variable `modis_snow` uses MODIS/061/MOD10A1 `NDSI_Snow_Cover`: units **NDSI index (0–100)**, nominal 500 m native grid, daily composite labels and catchment area weighting. The fraction is accepted raster area divided by total catchment raster area; it is not a snow fraction. See [methods.md](methods.md).

## Requirement import

The CSV requires `start`, `end` and nonnegative `requirement_m3s`. The sidecar supplies `name`, `intended_user`, `source`, `status`, `units`, `meaning` and `resilience`. Status is `scenario` or `documented`; units must be `m3/s`. Use `resilience="unknown"` unless evidence supports a more specific statement.

A requirement must cover the whole flow interval being assessed. If it changes inside a daily or monthly mean-flow interval, that interval's exposure is unresolved; the application does not invent a finer flow profile. Requirement gaps reduce assessed coverage. Historical baseline values are not requirements unless the user explicitly defines and labels such a scenario.

## Calendars and forecast tables

NVE daily labels are mapped to fixed Norwegian standard-time day intervals (`Etc/GMT-1`, UTC+1). The Swiss archive supplies dates without established subdaily timing; these are represented as nominal UTC 24-hour days and retain that limitation. MODIS product dates use nominal UTC labels for composites and do not imply simultaneous observations with flow.

Forecast rows use `start`, `end`, `estimate_m3s`, `p10`, `p90` and `count`. They represent complete calendar months. The current p10–p90 band is historical variability, not a prediction interval. A future model offering calibrated prediction intervals must identify them separately; monthly output must not be expanded into claimed daily shortage events.

## Export and errors

Evidence ZIPs contain `observations.csv`, `baseline.csv`, `periods.csv`, optional `nasa_driver.csv`, optional `outlook.csv`, `evidence.json` and an explanatory README. JSON uses `null` for unavailable numerical values. Provider messages, request settings, geometry, source metadata and methodological limitations accompany the results. Credentials and environment settings are excluded.

Schema violations raise input errors. Provider states distinguish authentication, retryable pending work, unsupported requests, no data and other failures. No state authorizes automatic substitution with synthetic data.
