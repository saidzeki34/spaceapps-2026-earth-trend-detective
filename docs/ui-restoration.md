# Claude UI restoration - 2026-11-15

The user rejected the industrial redesign from PR #14 and requested Claude's interface back, with the real trend data connected. Work started from clean main at aeae844. The restoration source is Claude's submitted UI at 01c421a, preserved on archive/ui-handoff-20261115.

## Scope

The original occupation screen, visual style, map-first Europe/country/river navigation, sidebar, resizable results area and timeline are restored. Additional backend analyses and their controls use those existing containers. This is a data integration into Claude's interface, not a new dashboard design.

The read-only adapter, saved-data availability states, Plotly/backend figures and tables, full CSV export, reload and verified river segments remain. Norway/GLDAS sources show build instructions when absent. Gauge selection and years refer to actual saved records. Occupations add no fabricated requirements; risk and physics/prediction remain unfinished. The only synthetic content is the separately labelled 3D surface demonstration.

Jonathan's trend code, saved datasets and tests are unchanged. Original branches remain intact. PR #14 and feature/industrial-results-ui preserve the industrial version without resetting or rewriting main.

## Verification

- The 32 focused UI backend, HTTP server and river-geometry tests passed in 42.74 seconds. JavaScript syntax and Git whitespace checks passed.
- Headless Chrome verified the occupation screen, Europe/country/river navigation, all 33 CAMELS gauges including the three cross-border stations, real monthly/daily plots, multiple variables (up to four), saved hydrological years, usual-year comparison, regional heatmaps and station-network analyses.
- CSV verification exported all 366 daily records for the selected year plus a header while displaying only 40 table rows per page. Page navigation and missing-value handling remain separate from export.
- Missing GLDAS comparisons and Norwegian builds show the backend build command without a chart or stale export. A simulated reload failure cleared the prior chart/table and disabled export; restoring the request and reloading recovered the selected analysis.
- Expand, fullscreen/Escape, the draggable map divider and the separately labelled synthetic 3D surface were checked. The surface cannot export observed records. Narrow-screen panel stacking was verified at 390 px with no page-width overflow.
- Independent read-only software review checked API mapping, request cancellation, state clearing, exports and map contracts. Its aggregate-scope and paired-coverage wording findings were corrected.
- The diff from aeae844 leaves `mountain_water/trend`, `tests/trend`, the Python UI backend and HTTP server unchanged. Existing branches and earlier UI versions remain preserved.

These checks cover software behavior, not scientific validation. Local saved data contained CAMELS-CH and Swiss station results; Norway and GLDAS were tested as unavailable sources, not as live successful downloads. Scientific interpretation, source/imagery licensing review and the unfinished risk/prediction work remain team responsibilities.
