# Claude UI restoration ? 2026-11-15

The user rejected the industrial redesign from PR #14 and requested Claude's interface back, with the real trend data connected. Work started from clean main at aeae844. The restoration source is Claude's submitted UI at 01c421a, preserved on archive/ui-handoff-20261115.

## Scope

The original occupation screen, visual style, map-first Europe/country/river navigation, sidebar, resizable results area and timeline are restored. Additional backend analyses and their controls use those existing containers. This is a data integration into Claude's interface, not a new dashboard design.

The read-only adapter, saved-data availability states, Plotly/backend figures and tables, full CSV export, reload and verified river segments remain. Norway/GLDAS sources show build instructions when absent. Gauge selection and years refer to actual saved records. Occupations add no fabricated requirements; risk and physics/prediction remain unfinished. The only synthetic content is the separately labelled 3D surface demonstration.

Jonathan's trend code, saved datasets and tests are unchanged. Original branches remain intact. PR #14 and feature/industrial-results-ui preserve the industrial version without resetting or rewriting main.

## Verification

Final checks will be recorded after browser verification of the restored interface. These checks cover software behavior, not scientific validation.
