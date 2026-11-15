# UI completion ? 2026-11-15

Historical record of PR #14. The user subsequently requested restoration of Claude's original UI appearance and workflow; see [UI restoration](ui-restoration.md). The data integration remains in use.

The user asked to finish the pasted UI brief and inspect what Claude had delivered. The starting checkout was clean main at 67d8d1b. The transcript ended in research/design planning; the disk still contained the older cream/serif UI, filled catchment polygons and imaginary data generators.

## Preserved and reused

Claude's local launcher, standard-library server and vendored Leaflet remain the basis of the interface. Jonathan's trend source and tests are unchanged. Existing submissions and preservation branches remain intact; the old UI is on archive/ui-handoff-20261115. The superseded generated application was not restored.

Read-only inspection found real saved Swiss results for 33 selected catchments and a saved 100-station Swiss network. The network's metadata records 1981?2020, baseline 1981?2000 and CAMELS-CH v0.9. No Norway or GLDAS processed directories were present here. Earlier team documentation about other live runs does not prove those outputs are available in this checkout.

## Delivered scope

- Industrial single-font dashboard with compact controls, square panels, tabular numbers and backend figures/tables.
- Direct UI adapter for Swiss/Norwegian observations, GLDAS comparisons and station views. Missing/corrupt products are explicit; saved-data refresh requires no restart.
- Removal of fabricated river records, evaporation, occupational requirements, risk scores, predictions and physics stand-ins. The separate 3D surface is labelled synthetic and carries no operational interpretation.
- Actual cached river segments where a conservative gauge match is available, and honest point-only fallback elsewhere. No catchment polygon is presented as a river.
- Documentation and focused UI checks. No trend algorithm changes, observation downloads, hosted deployment or service/editor integrations.

## Remaining work

Teammates must supply/build missing Norway and GLDAS outputs with their own credentials. Risk assessment, prediction and shared coordination are still placeholders. River matches are visual aids and require human geographic review; unmatched courses are reported. Scientific methods and claims still require team review.

## Verification

- 32 focused UI tests passed: saved-source availability/corruption, null handling, selection validation, source-comparison coverage, reload, HTTP routes, retired endpoints, static-file boundaries and conservative geometry matching. Synthetic fixtures validate software behavior, not scientific findings.
- Read-only sweep of existing local outputs: all 14 Swiss noncomparison figure/table pairs and all three station pairs rendered. Missing Norway/GLDAS products returned unavailable states; successful model comparison and differing coverage were checked with synthetic fixtures.
- Chromium browser checks covered real saved figures, station month/year heatmaps, station driver scatter, unavailable sources, multi-variable series, chart expansion, reload, pagination, mobile width and the rotatable labelled 3D surface. Deliberately failing reload cleared stale export state; the next reload recovered. No page/console/network errors were reported by the successful browser runs. Screenshots remain local in ignored tmp/ui-browser/.
- Both authored JavaScript modules passed Node syntax checks; UI CLI help and git diff --check passed. No difference exists under mountain_water/trend or tests/trend versus the submitted main. The slow unchanged backend suite was not rerun for this UI task.
- Independent assistant integration review found and resolved inaccurate comparison-period headers, a source-comparison map-selection transition, stale CSV state after failed reload, and a wide-table layout overflow. These checks do not constitute human scientific review.

The local map display contains 22 matched river-segment features and 11 unavailable explanations for the selected CAMELS product. Gauge country and exact outlet coordinates retain their source metadata; the product includes neighboring-country gauges, so its 33 records are not all geographically inside Switzerland.
