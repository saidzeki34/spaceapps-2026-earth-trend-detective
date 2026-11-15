# Decision log

| Date | Decision | Basis |
| --- | --- | --- |
| 2026-10-30 | main/develop and feature PR workflow proposed | Historical administration record |
| 2026-11-15 | Preparation ended; user explicitly confirmed competition start | User instruction |
| 2026-11-15 | Latest scope is documentation, module responsibilities, folders and empty files only; teammates write code | User correction supersedes the broader handoff |
| 2026-11-15 | Preserve generated implementation separately at archive/generated-implementation, commit 165e09b | Nothing lost; archive is not accepted main implementation |
| 2026-11-15 | Verify main remained at 6576023 with only prior administrative/research content before skeleton work | Remote inspection; no implementation revert needed |
| 2026-11-15 | Shared skeleton and future feature PRs target main; preserve develop/work/* | User's shared starting-point request |
| 2026-11-15 | No algorithms, integrations, UI, models, database schemas or tests in this delivery | Explicit scope limit |
| 2026-11-15 | Reorganize placeholders into ui and trend first, risk_assessment later, predictionmodel much later; shared holds common inputs and source access | User's section proposal; documentation and empty files only |
| 2026-11-15 | Move historical analysis to trend, figures to ui/charts, models to predictionmodel and data/services/contracts/config to shared; add subsection placeholders | No implementation imported from the archive; risk_assessment uses the corrected spelling |
| 2026-11-15 | Backend MVP starts in mountain_water/trend on work/backend/feature/camels-ch-trends (from work/backend/feature/mvp) | User approved backend plan with adjustments |
| 2026-11-15 | Data: CAMELS-CH (Zenodo), observed daily series only; static attributes for filtering, labels and maps. Switzerland only; Norway, NASA data and forecasting deferred | User decision |
| 2026-11-15 | Mountain filter defaults: mean elevation >= 1500 m, area <= 500 km², no reservoirs, >= 30 valid years; no glacier/non-glacier separation | User decision; thresholds remain tunable |
| 2026-11-15 | Hydrological year Oct–Sep; 10-year comparison windows; Sen's slope + Mann-Kendall (trend-free pre-whitening) with Benjamini-Hochberg FDR | Plan approved by user; Hamed-Rao variance correction rejected because it returned undefined p-values for strong trends |
| 2026-11-15 | GLDAS backend on feature/backend-gldas (from work/backend at 4324808): GLDAS-2.1 Noah 0.25° 3-hourly, aggregated to daily | User choice among GLDAS-2.0/2.1/2.2 options |
| 2026-11-15 | GLDAS locations: the CAMELS-CH mountain selection, area-weighted over catchment outlines; variables: runoff (surface + baseflow), snowmelt, precipitation, snowfall, temperature, evapotranspiration, SWE (no soil moisture) | User decision |
| 2026-11-15 | GLDAS windows: 10-year steps, final window kept if >= 5 years; >= 20 valid years required | User decision; record starts 2000 |
| 2026-11-15 | Access via Giovanni Time Series API, not Hydrology Data Rods | GES DISC announced Data Rods discontinuation (no earlier than 2025-10-31) |
| 2026-11-15 | Norway backend on feature/backend-nve (from feature/backend-gldas): NVE HydAPI daily discharge, NVE catchment outlines, seNorge precipitation/temperature/SWE via NVE GridTimeSeries | User request; seNorge chosen as local drivers |
| 2026-11-15 | Norway filter: median catchment elevation >= 800 m, area <= 500 km², unregulated (any regulation/reservoir metadata > 0 excludes), >= 30 valid years; period 1961–latest, 10-year windows (final >= 5 years kept) | User decision |
| 2026-11-15 | GLDAS-2.1 comparison also for the Norwegian selection (`--region no`), same variables and method as Switzerland | User request |
| 2026-11-15 | Norway regulation: NVE's catchmentRegTypeName decides (only categories starting "uregulert" kept); numeric reservoir fields only when no category | inspect showed regulated stations with all numeric regulation fields at 0 |
| 2026-11-15 | seNorge drivers sampled on a regular grid of ~20 points per catchment and averaged, using GTS point series | GTS polygon endpoint returned HTTP 500 for every request, including NVE's documented example |
