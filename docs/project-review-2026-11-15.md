# RivaScope: scientific, software and judge-readiness review

Reviewed on **15 November 2026**, against main commit **`3f0db61b7f70de5b3b32546decefb399f79d18b7`** and the saved datasets on this PC. This is an assessment and proposed work list, not a record of fixes. No application code, UI design, scientific outputs or branches were changed for this review.

**The project is a working historical exploration prototype. Its main weakness is the evidence behind its interpretation, rather than its appearance.** It connects substantial real data and useful analyses, but several provenance and calendar defects affect calculations. Its historical screening does not establish operational risk, climatic causation or future water availability. Those distinctions should govern the demonstration and pitch.

The review covers first-party trend, ingestion, risk and UI/server code, saved-output summaries, packaging, tests, repository access, documentation and source references. It does not certify every provider record, audit vendored libraries, establish production security, or replace a hydrologist's review. Findings below distinguish **confirmed defects**, **documented limitations**, **validation gaps** and **delivery risks**.

## Read these priorities first

| Priority | Finding | Evidence and immediate implication |
| --- | --- | --- |
| Before claiming observed-only results | NVE provider correction flags are dropped | Raw records distinguish interpolation, reconstruction and incomplete source data; processed records lose that distinction. Hiding locally filled days does not remove provider-filled values. |
| Before stronger timing/variability claims | Incomplete calendars and removed years affect calculations | 70 Norwegian annual timing rows use incomplete calendars. Enforcing adjacent dates changes 5 Swiss and 53 Norwegian annual flashiness values. |
| Before precise daily NASA comparisons | GLDAS flux intervals are assigned to the wrong daily boundary | Backward three-hour accumulations/averages are grouped by timestamp date. Daily flux windows are effectively shifted by three hours. |
| Before calling results basin-wide | GLDAS missing cells are silently renormalized | A tiny available fraction can supply the reported mean for the entire catchment. Actual affected saved dates have not been counted. |
| Before claiming significance or explaining causes | Inference and uncertainty need more validation | Missing years are compressed in pre-whitening; some exploratory tests are unadjusted; no demonstrated sensitivity envelope or dependence-aware intervals accompany headline results. |
| Before judge handoff | Code access and reproduction are incomplete | The GitHub repository was verified **private**. Data are local/ignored; no frozen build/environment manifest or independent reproduction was demonstrated. |
| Before relying on the demo under pressure | Startup and table requests do unnecessary work | All five sources load eagerly; one table transferred 6.7 MB for 20,088 rows, even though the browser displays a page at a time. |

These priorities do **not** mean the whole application should be rewritten. Most corrective work concerns data contracts, calculations, labels, validation and delivery. The UI's visual design can remain intact.

## What is already implemented well

- Saved Swiss observations, Norwegian discharge/environmental data, Swiss and Norwegian GLDAS builds, and a combined station network are connected to figures and tables. The local selections contain **33 Swiss catchments, 84 Norwegian catchments and 184 stations** in the separate network view.
- The main trend analysis calculates Sen slopes using actual years, attempts autocorrelation adjustment and applies false-discovery-rate correction across gauges within each metric.
- Missing data generally remain missing. Locally interpolated discharge has flags, and daily record plots hide those fills. GLDAS is identified as model runoff, and the historical risk adapter rejects it as a substitute for observed discharge.
- The risk calculation regularizes the calendar, requires complete seasons/years for its main coordinates, and censors threshold episodes at missing-data and season boundaries. Its warnings distinguish historical scenarios from forecasts and operational failure.
- CAMELS downloads have version/checksum records; GLDAS has unit checks and saved grid weights; raw data and credentials remain outside Git. Teammate histories and the accepted submissions are preserved.
- The map deliberately leaves unverified connections absent. Its **77/117 matched gauges and 40 unavailable courses** are documented; this is preferable to inventing river or lake connections. These are display matches, not a validated source-to-mouth hydrological network. See the [map guide](../mountain_water/ui/map_component/README.md).

These are meaningful safeguards. They do not, by themselves, validate the scientific conclusions.

## Scientific and data weaknesses

### S1. Norwegian provider corrections disappear from the processed contract — confirmed defect

[nve.py:307](../mountain_water/trend/nve.py#L307) keeps date, discharge and quality but drops HydAPI's `correction` field. The risk calculation masks only this project's `discharge_vol_filled` flag ([assessment.py:24](../mountain_water/risk_assessment/assessment.py#L24)). Provider corrections are therefore not distinguishable from other discharge in the processed data.

The raw cache for the **84 selected Norwegian gauges**, including years later excluded, contains:

| Provider correction | Raw cached records | Meaning |
| --- | ---: | --- |
| 2 | 44,790 | Interpolation |
| 3 | 25,255 | Calculated from models or other series |
| 12 | 1,861 | Incomplete source observations |
| 13 | 242 | Adjusted using a similar station |

These are **not counts of retained rows in the final processed table**, and corrected observations are not automatically unusable. The defect is loss of provenance and the absence of an explicit acceptance policy. Quality codes are also retained without being used as an analysis filter. The provider distinguishes quality and correction; both need preservation. [NVE HydAPI documentation](https://hydapi.nve.no/UserDocumentation/).

**Needed:** retain both fields through processing/export; agree accepted categories; count their contribution to each result; compare headline results under plausible policies. Until then, avoid “only directly measured values” or “all interpolated data removed.”

### S2. The main timing calculation accepts incomplete years — confirmed saved-data effect

[timing.py:15](../mountain_water/trend/timing.py#L15) accepts at least 360 rows with no remaining NaNs. It does not establish that every expected calendar date exists. A synthetic 360-day constant series returns finite timing, including half-volume day 180.

**70 Norwegian saved annual rows have finite timing from incomplete calendars:** 68 contain 364 of 365 days, one contains 363, and one contains 362. Of these rows, 69 belong to HY 2026 and one to HY 1991. HY 2026 examples include gauges `103.1.0`, `103.20.0`, `103.3.0` and `104.22.0`; their daily records end on **2026-09-29**. This review did not establish why September 30 is missing. No analogous Swiss finite-timing case was found in this check.

The risk implementation correctly requires a complete regular calendar, so the two paths can disagree about usable years. **Needed:** validate dates against the expected hydrological year before timing calculations; regenerate affected results and quantify changes. A small missing fraction is not proof of negligible timing bias, especially near a seasonal transition.

### S3. Removing years can turn long gaps into daily changes — confirmed saved-data effect

[pipeline.py:198](../mountain_water/trend/pipeline.py#L198) removes rejected years before metrics run. [variability.py:11](../mountain_water/trend/variability.py#L11) then uses row-to-row differences without checking date adjacency.

A read-only recalculation that accepts only genuine one-day differences changes **5 Swiss and 53 Norwegian annual flashiness values**. Maximum absolute changes are approximately **0.00229** and **0.01478**, respectively. The impact on final flashiness trend signs/significance was not recalculated.

The seven-row rolling calculation in [flow_metrics.py:22](../mountain_water/trend/flow_metrics.py#L22) has the same structural vulnerability. However, **zero saved annual `min7_flow` values changed** in the continuity probe. That distinction matters: a reproducible risk in code is not proof that every stored metric is wrong.

**Needed:** regular calendars or explicit continuity checks for differences and rolling windows, followed by targeted regeneration and before/after comparisons.

### S4. GLDAS fluxes use the wrong daily interval boundary — confirmed defect

[gldas.py:161](../mountain_water/trend/gldas.py#L161) groups all timestamps using `floor("D")`. NASA defines accumulated and time-averaged variables as covering the **preceding three hours**. A midnight flux belongs to the previous day's final interval; instantaneous states need separate semantics. [NASA GLDAS-2 README, temporal definitions](https://docserver.gesdisc.eosdis.nasa.gov/public/project/hydrology/README_GLDAS2.pdf).

A minimal reproduction with eight unit accumulations timestamped January 1 at 03:00 through January 2 at 00:00 should produce January 1 total 8. The current function produces NaN on both dates because it splits those eight intervals into groups of seven and one. Real cached runoff/precipitation responses start at 03:00, so this is relevant to the input format.

Within longer records, the daily flux window is effectively **21:00–21:00 UTC**, labeled as a calendar day. Daily alignment and boundary totals are affected; the size of the effect on saved annual trends is **not yet measured**.

**Needed:** variable-specific interval handling, boundary examples against raw responses, and comparison of old/new daily and annual outputs. Do not shift every state variable blindly.

### S5. Missing GLDAS spatial coverage can become a complete-looking basin value — confirmed behavior, extent unmeasured

[catchment_grid.py:94](../mountain_water/trend/catchment_grid.py#L94) renormalizes weights over available cells without returning a valid-area fraction or imposing minimum coverage. [gldas.py:286](../mountain_water/trend/gldas.py#L286) then converts the result using the full basin area.

A probe with **1% valid area at value 100 and 99% missing area returns basin value 100**. The number of actual saved basin-days affected has not been established. Fixed lake/land masks and temporary missing inputs also need different interpretation.

**Needed:** coverage per variable/day, an explicit land-mask policy, acceptable support thresholds and comparisons using common spatial support. Daily completeness alone cannot establish spatial completeness.

### S6. Fine map geometry overstates the spatial detail of the NASA model unless explained — scientific limitation

GLDAS here is **0.25-degree Noah model output**, not a measurement at each river. [NASA GLDAS overview](https://ldas.gsfc.nasa.gov/gldas). Converting runoff depth to cubic metres per second using basin area does not route water to the gauge or model lakes, travel times and management. NASA also documents missing glacier physics and additional uncertainty in high-altitude/high-latitude settings. [NASA GLDAS-2 README](https://docserver.gesdisc.eosdis.nasa.gov/public/project/hydrology/README_GLDAS2.pdf).

Saved grid-weight metadata show:

| Selection | Unique cells | Entirely within one cell | At least 90% weight from one cell | Smallest polygon |
| --- | ---: | ---: | ---: | ---: |
| 33 Swiss catchments | 45 | 8 | 11 | about 8.12 km² |
| 84 Norwegian catchments | 177 | 14 | 22 | about 1.64 km² |

Neighbouring small catchments may share most of their model signal. These counts describe resolution, not validation performance. “Runoff leads discharge” is not guaranteed in every comparison merely because routing is absent.

**Needed:** explain NASA's role as environmental/model context; benchmark seasonal bias and timing differences; stratify checks by basin size and glacier influence. Do not infer a river-scale forecast from a precise-looking map.

### S7. Calendar alignment and snow resets can distort seasonal interpretation — confirmed inconsistencies

**Leap alignment:** [baseline.py:21](../mountain_water/trend/baseline.py#L21) and [seasonal.py:28](../mountain_water/trend/seasonal.py#L28) drop hydrological day 366. For October years, this drops leap-year September 30, not February 29. Non-leap March 1 and leap February 29 both occupy day 152. A probe with values 1 and 9 on those dates produces a shared median of 5. Reference bands and regimes consequently mix adjacent calendar dates after February. The risk baseline uses month/day grouping and avoids this specific issue.

**SWE resets:** [drivers.py:18](../mountain_water/trend/drivers.py#L18) searches the whole hydrological year for SWE falling below 5% of its peak. [stations.py:221](../mountain_water/trend/stations.py#L221) already documents September resets and restricts its search to January–August. The main driver path lacks that safeguard. Swiss gauge **2109** has SWE **193.14 mm on 1999-09-01 and 0 on September 2**, with main-trend melt-out day 337. This is a concrete reset-sensitive example, not independently verified physical melt.

There are 143/695 Swiss and 412/3,593 Norwegian finite main-trend melt-out records at day 336 or later. **These are inspection candidates, not counts of proven contamination.**

**Needed:** consistent calendar conventions and source-aware snow-reset handling; inspect flagged examples and recompute relevant driver relationships.

### S8. Different variables use different completeness rules — confirmed methodological inconsistency

The main pipeline accepts years with at least **90% original discharge coverage** and interpolates gaps of up to five days. Volume is available-day mean multiplied by row count. Annual precipitation can be a partial sum with only 300 values, while temperature means have no minimum count ([flow_metrics.py:20](../mountain_water/trend/flow_metrics.py#L20), [drivers.py:35](../mountain_water/trend/drivers.py#L35)). Missing temperature is treated as false by the snowfall proxy's `<= 0` test, making corresponding precipitation contribute zero estimated snowfall.

Synthetic probes show what this permits: 305 days of 1 mm precipitation plus 60 missing days yields an “annual” total of 305 mm; one valid temperature of 10°C yields annual mean 10°C. **This does not establish that current saved temperature results use one day.**

Among selected annual records, 10 Swiss and 125 Norwegian rows have less than complete original discharge coverage. Saved locally filled discharge counts are 7 Swiss and 179 Norwegian. Risk uses complete unfilled seasons/years instead.

**Needed:** per-variable coverage requirements, common-support rules for relationships, and explicit separation of measured, interpolated and extrapolated totals. Otherwise apparent relationships can include changes in coverage.

### S9. Significance handling is a useful start, but not a fully validated inference pipeline

**Irregular years:** Sen slope uses actual years, but [trends.py:32](../mountain_water/trend/trends.py#L32) drops missing values before pre-whitening and passes no year spacing. Adjacent retained observations may be years apart. Nonconsecutive usable years occur in **103/950 Swiss observed trend rows (4 gauges)** and **1,032/2,349 Norwegian rows (56 gauges)**; also 1/990 Swiss and 3/2,518 Norwegian GLDAS rows. These counts do not prove those significance decisions false. They identify where the dependence model needs justification. The [pyMannKendall implementation](https://github.com/mmhs013/pyMannKendall/blob/master/pymannkendall/pymannkendall.py) operates on a sequence of values.

**Multiple testing:** BH/FDR correction is applied across gauges **per metric** in the trend/station tables. Driver correlations, window Mann–Whitney tests and trend/attribute correlations use unadjusted p-values ([drivers.py:106](../mountain_water/trend/drivers.py#L106), [comparison.py:33](../mountain_water/trend/comparison.py#L33), [plots.py:246](../mountain_water/trend/plots.py#L246)). Exploring many metrics, windows and stations creates more opportunities to find apparently interesting results. Spatially related catchments are not independent replications.

**Uncertainty:** main slopes lack confidence intervals or a demonstrated sensitivity envelope. Risk discards the interval outputs from `theilslopes` and explicitly warns that it has no dependence-aware intervals. Adding a library's default interval alone would not resolve temporal dependence, selection or measurement uncertainty. [SciPy Theil–Sen documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html).

**Needed:** define the family of scientific claims; distinguish adjusted from exploratory findings; check temporal/spatial dependence; report effect size, support and appropriate uncertainty; vary periods, completeness, interpolation and baseline choices. Do not equate “not significant” with “stable” or “no change.”

### S10. Decade labels, country labels and source comparisons can conceal different samples

- A globally defined ten-year window need not contain ten usable years for a particular gauge/metric. [comparison.py:25](../mountain_water/trend/comparison.py#L25) calculates means with as few as one value, although its test needs five. Saved comparison rows with **1–4 values**: **148 Swiss, 1,323 Norwegian, 1 Swiss GLDAS and 6 Norwegian GLDAS**. These are metric/window rows, not distinct catchments. Display and interpretation should use the stored `n_years`.
- Swiss catchments use mean elevation ≥1500 m; Norway uses median elevation ≥800 m. The separate station network selects 100 eligible Swiss streams with complete 1981–2020 records and inherits the Norwegian selection. Record periods and calendar/hydrological-year conventions also differ ([settings.py](../mountain_water/trend/settings.py), [stations.py:150](../mountain_water/trend/stations.py#L150)). These are selected networks, not representative national samples.
- [nve.py:195](../mountain_water/trend/nve.py#L195) treats missing regulation metadata with no positive recorded field as unregulated. Unknown is not evidence of absence. Missing selection columns can also cause filters to be skipped with warnings.
- [sources.py:55](../mountain_water/trend/sources.py#L55) merges observed/model year keys but fits slopes separately; metric-specific missingness can produce different effective years. Annual bias/correlation correctly uses paired nonmissing values. The saved magnitude of the slope-comparison issue was not measured.

**Needed:** common cohorts/periods for country comparisons, explicit unknown regulation status, minimum support per window, and paired metric-specific years for model comparisons. Avoid “Norway changes faster than Switzerland” without these checks.

### S11. Environmental inputs are derived products with unresolved spatial/time support

The seNorge adapter samples approximately 20 regular points per basin, with a representative-point fallback, then averages available series ([nve.py:283](../mountain_water/trend/nve.py#L283), [nve.py:471](../mountain_water/trend/nve.py#L471)). This is an approximation to basin averaging; it has not been shown to converge against full 1 km grid aggregation. Mountain elevation gradients, polygon edges and missing sample points can matter. Valid-point counts and uncertainty are not carried through.

Daily intervals also differ. HydAPI dates are converted to Oslo dates; seNorge/GTS time-of-day is discarded; the exact selected theme's date convention needs verification. MET Norway documents 06:00-based precipitation intervals and variable-specific timing. GTS unit/name metadata are not checked and propagated like GLDAS units. [MET Norway variable definitions](https://github.com/metno/seNorge_docs/wiki/Variables), [NVE GTS documentation](https://api.nve.no/doc/gridtimeseries-data-gts/).

CAMELS-CH's gauged discharge does not make every environmental variable a direct measurement: SWE includes snow modeling/assimilation and has a shorter record. [CAMELS-CH paper](https://essd.copernicus.org/articles/15/5755/2023/).

**Needed:** a per-variable contract covering provider/product, measured versus derived, units, timezone, interval, spatial support, quality flags and coverage; sampling-density sensitivity on a small representative basin set.

### S12. “Attribution” and “risk” must remain bounded claims — documented limitations

**Attribution:** [drivers.py:124](../mountain_water/trend/drivers.py#L124) regresses flow anomalies on precipitation/temperature and assigns the remainder to a residual. The components sum to the observed change by construction. A test of that identity is not independent causal validation. There is no demonstrated causal identification, confounder control, uncertainty propagation or independent evaluation of the decomposition. The residual is not measured glacier melt.

**Risk:** [risk-rules.js:1](../mountain_water/ui/web/js/risk-rules.js#L1) uses prototype boundaries of 5%/decade volume change, 3 days/decade timing and 15% variability; stronger boundaries are 10%, 7 days and 30%. These are uncalibrated screening rules, not probabilities or operating limits. Variability includes the trend. A user-supplied constant flow threshold does not model demand schedules, allocations, ecological constraints, intake capacity, water quality/temperature, storage or alternatives. The existing warnings and “not determined” state are strengths.

The main headline and modal also measure different things: annual versus selected-season volume, whole-period mean versus fixed baseline normalization, and **trend in daily-flow CV** versus **interannual seasonal-volume variability**. Different numbers are not necessarily conflicting results. They need definitions and common-period comparisons before being interpreted together.

**Needed:** present descriptive analysis as descriptive. Validate any future operational classification against real requirements and outcomes. Prediction remains an explicit unimplemented scope, not a capability demonstrated by historical trend lines or 3D surfaces.

### S13. Product revisions and caches can undermine reproducibility — confirmed behavior and validation gaps

- NVE discharge is cached by gauge ID; existing files and station metadata are reused regardless of an extended requested end date ([nve.py:382](../mountain_water/trend/nve.py#L382), [nve.py:409](../mountain_water/trend/nve.py#L409), [nve.py:428](../mountain_water/trend/nve.py#L428)). Resuming a download is not the same as refreshing it. seNorge selection uses the lexically last cached filename.
- GLDAS loads overlapping cached chunks and keeps the first duplicate timestamp; revision preference is not explicit. CAMELS defaults to latest and rewrites `retrieved_at` on cache reuse; its root selection is lexical rather than semantic version ordering.
- Processed metadata records settings and important source information, but does not bind outputs to a code SHA, dependency lock and complete input/output hash manifest ([pipeline.py:240](../mountain_water/trend/pipeline.py#L240)). The checksum recorded in local CAMELS v0.9 provenance matches its [published record](https://zenodo.org/records/15025258); the ZIP was not independently rehashed during this review. This is a metadata consistency check, not complete build reproducibility.
- NASA documents a **June 9, 2025 radiation-forcing change**, within the local GLDAS period. Its influence on these results has not been tested. This is a sensitivity question, not proof of an artificial trend. [NASA GLDAS-2 README](https://docserver.gesdisc.eosdis.nasa.gov/public/project/hydrology/README_GLDAS2.pdf).

**Needed:** distinguish retrieval/reuse/build times; record requested and actual coverage; define refresh/version rules; freeze code, dependency versions, source identifiers and file hashes for the demonstration. Compare relevant results with/without HY 2025 before attributing a discontinuity.

## Software bottlenecks and reliability

The measurements below are single samples from a read-only process on this PC, using current saved datasets. They are **not production benchmarks or universal timings**. An unusually slow cold import may reflect machine, storage/OneDrive or concurrent-work conditions; its cause was not isolated.

| Operation | Measured time | Size/work |
| --- | ---: | --- |
| Import backend and dependencies | 103.438 s | One unusually slow cold sample |
| First catalogue after imports | 7.843 s | 281,336-byte JSON |
| Warm catalogue | 1.207 s | Still scans options |
| CH gauge 2109, discharge + temperature figure | 2.082 s first; 0.358 s repeat | 41,176 bytes |
| First Norwegian gauge, flow surface | 0.784 s first; 0.511 s repeat | 224,607 bytes |
| That surface's table | 1.586 s | **20,088 rows; 6,713,602 bytes** |

Summed DataFrame deep-memory estimates for the five cached sources are **715.5 MiB**: CH 110.2, Norway 328.7, CH GLDAS 76.2, Norway GLDAS 197.6, stations 2.8. This can count shared objects more than once and excludes other process allocations; it is **not measured process RAM**. The separate process-memory probe failed, so no RAM claim is made from it.

| Issue | Evidence and consequence | Suggested response |
| --- | --- | --- |
| Eager loading and repeated scans | [backend.py:189](../mountain_water/ui/backend.py#L189) loads all five sources. `_options()` scans complete daily frames, including through `_views()`; figure/table requests repeat this work. `/api/courses` also calls the whole catalogue. A global lock covers dataset loads. | Cache options/catalogue by build identity; load selected sources/columns lazily; obtain one source's map metadata directly. |
| Pagination happens after transfer | [backend.py:466](../mountain_water/ui/backend.py#L466) selects and serializes all daily rows; [main.js:631](../mountain_water/ui/web/js/main.js#L631) receives them before slicing pages and constructing another CSV representation. | Server pagination for viewing, streamed CSV for export, optional date/column selection. Preserve flags and attach provenance/context. |
| Cancelled requests can keep computing | Browser fetch aborts do not cancel Python work; [server.py:48](../mountain_water/ui/server.py#L48) uses request threads without a bounded calculation queue or figure cache. Actual overload was not demonstrated. | Coalesce/cache identical requests and measure rapid selection changes before claiming multi-user scale. |
| Rebuilding can expose mixed versions | [pipeline.py:83](../mountain_water/trend/pipeline.py#L83) overwrites tables sequentially. Cache identity is modification time/size; there is no atomic complete-build switch. A concurrent mixed read was not reproduced. | Versioned staging builds and atomic activation. For the demo, finish builds before launching/reloading. |
| One tab can stop another tab's server | `pagehide` sends `/api/bye`; [server.py:113](../mountain_water/ui/server.py#L113) sets a shared shutdown timer without tracking other idle clients. Confirmed code path, not browser-reproduced in this audit. | Demo with `python -m mountain_water.ui --no-window`, then open the URL. Later track sessions or use explicit shutdown. |
| Unnecessary static reloads | [server.py:124](../mountain_water/ui/server.py#L124) sends `no-store` even for roughly 4.85 MB of Plotly JavaScript and static geometry; no compression is configured. | Versioned static caching and appropriate API freshness. Profile before adding infrastructure. |
| Offline map limitation | Satellite/reference tiles are external Esri URLs; charts and saved geometry are local. | Rehearse offline. Do not promise offline satellite imagery. |
| Station screen scope differs from its header | [main.js:161](../mountain_water/ui/web/js/main.js#L161) requests the combined station network, while the country header retains the 33/84 observed-catchment context. Plots correctly contain both countries. | Correct scope/count wording or consistently filter the data. This requires no visual redesign. |

The current local server is bound to `127.0.0.1`; it is **not a deployed, multi-user service**. Authentication, hosting reliability and load guarantees are future work if deployment becomes a goal. This review does not imply that the local app is currently publicly exposed. [Python HTTP server documentation](https://docs.python.org/3/library/http.server.html).

## Delivery, maintenance and evidence gaps

**Judge access:** authenticated GitHub metadata confirmed `private: true` for [the repository](https://github.com/saidzeki34/spaceapps-2026-earth-trend-detective) during this review. An unauthenticated judge cannot inspect that code link. The team needs an approved accessible submission artifact/demo and should test it signed out. No visibility setting was changed.

**Installation:** [pyproject.toml](../pyproject.toml) has lower dependency bounds and no lockfile. There is no explicit runtime package-data configuration. In an ignored copy, `egg_info` produced a 67-file manifest with **zero web assets**. An offline wheel build could not finish because this environment lacks `bdist_wheel`; **a broken installed wheel was not tested or claimed**. Noneditable UI distribution remains unverified and the manifest is evidence of an asset-inclusion gap. The backend also assumes a checkout-relative data location. [Setuptools package-data documentation](https://setuptools.pypa.io/en/latest/userguide/datafiles.html).

**Independent reproduction:** a clean checkout does not contain the ignored observations or processed tables, and some downloads require credentials. There is no demonstrated clean-machine reproduction of the exact graphs. Provide pinned source/build metadata, dependency versions, exact commands and a permitted example or prepared artifact. Do not commit credentials or large raw data to solve this.

**Tests and automation:** tests cover useful implementation behavior, including synthetic science fixtures, risk, API and geometry. There is no committed CI workflow or persistent browser regression suite for the recently fixed interactions. Passing tests cannot establish scientific validity; several defects above exist outside their assertions. Preserve the tests and add focused cases for demonstrated failures when fixes are undertaken.

**Contracts:** the shared contract files remain empty while UI/risk code reads trend dataclasses and private adapter methods. This works today but makes future schema changes risky. A small versioned processed-data contract is more useful than filling every placeholder prematurely. Prediction and unused shared modules should remain clearly marked incomplete.

**Exports:** raw record tables can include flagged local interpolation while daily graphs hide it. That is documented, but CSV export omits API context/notes. An exported number may therefore lose its processing explanation. A provenance sidecar or metadata-bearing export would make results defensible outside the application.

**Documentation drift:** [project-brief.md:8](project-brief.md#L8) still describes the surface as a visual demonstration and assessment as unfinished; [CONTRIBUTING.md:9](../CONTRIBUTING.md#L9) says risk is unimplemented; [submission-checklist.md:3](submission-checklist.md#L3) says the delivery is empty placeholders. Retained architecture tables mention Streamlit. The [current UI guide](../mountain_water/ui/README.md) is more accurate. Keep historical handoffs, but make one current capabilities/limitations page authoritative.

**Licensing and credit:** no project-root license was found. Vendored Leaflet has a license; data and geometry attribution are recorded separately. Esri terms review remains marked pending in the ledger. Decide and record the project's license and complete the recorded source/asset review before describing the whole submission as openly reusable. AI assistance is already recorded, but the final submission should accurately reflect the actual contributors and accepted code. This review did not perform a legal audit or rewrite attribution.

**Impact evidence:** the repository explains possible users, but this review found no recorded customer interviews, validated demand schedules, operational outcomes or comparison against an existing workflow. That is absence of evidence in the repository, not proof the team has never talked to users. A single concrete user decision supported by a credible example would strengthen the pitch more than additional generic occupation labels.

## Questions judges are likely to ask

These are rehearsal questions based on the implementation and project purpose, not a claimed official 2026 rubric. The [official challenge's indexed summary](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/) emphasizes visualizing changes in Earth-system variables and evaluating where/how much change occurs, including statistical significance. Full official challenge/resources pages returned HTTP 502 during review, so current detailed submission rules and local judging requirements were not verified.

| Likely question | Defensible answer today / evidence to prepare |
| --- | --- |
| What does your project actually do? | It explores historical changes in selected mountain catchments using gauge records and NASA land-surface context, with optional historical threshold scenarios. It is not a validated forecast or operational decision system. |
| What is new compared with existing data portals? | The proposed contribution is connecting basin history, seasonal timing and a user scenario in one workflow. The statistics themselves are established. Demonstrate that workflow advantage; do not claim a new hydrological algorithm. |
| What is NASA data doing that the gauges cannot? | GLDAS supplies spatially consistent modeled environmental variables and runoff context. Show one concrete comparison/insight. A NASA logo or unused optional source is a weak answer. |
| Is GLDAS a satellite measurement of this river? | No. It is land-surface model output. Runoff-to-volume conversion is not routing, and small basins share coarse cells. |
| Are the plotted discharge values all directly measured? | Not established. Local fills are flagged, but NVE provider correction provenance is currently lost during processing. Explain S1 rather than claiming observed-only data. |
| What is your strongest result, and how large is it? | Prepare one verified gauge, variable, period, unit, effect size, coverage and uncertainty. Do not invent or select a headline solely because its p-value looks attractive. |
| How do you know the result is statistically significant? | Main trend tables use pre-whitening and BH correction per metric. Missing-year treatment and exploratory tests still require validation. Show the adjusted result and the exact tested family. |
| How many things did you test before finding this result? | Report gauges, metrics, windows and any filtering/selection. Distinguish exploratory displays from a prespecified claim. |
| Could missing data or interpolation cause the trend? | Potentially. Coverage rules vary and provider fills are not fully represented. Prepare complete-case, no-fill and quality-policy sensitivity comparisons. |
| Are your seven-day quantities seven consecutive days? | Not guaranteed in the current main pipeline after year filtering. Flashiness changes were reproduced; saved seven-day minima did not change in the audit. |
| Do all dates mean the same measurement day? | Not yet fully verified. GLDAS flux grouping has a three-hour boundary defect; other sources use different local/UTC intervals. |
| How are snow resets and leap years handled? | Risk/station paths contain safeguards that the main trend path does not consistently share. The review identifies specific calendar/reset cases requiring correction. |
| Why these stations, and can you generalize to whole countries? | They are selected mountain networks with different elevation criteria and record designs. National representativeness has not been established. |
| Why does the Switzerland screen include Norway or 184 stations? | The station view is a separate combined network, not the 33-catchment Swiss selection. Its surrounding header needs clearer scope. |
| Why do the headline and risk popup show different numbers? | They use different seasons, normalization baselines, coverage rules and variability definitions. Compare definitions and common years before comparing values. |
| Did climate change or glacier loss cause this? | The current associations and regression decomposition do not identify cause. The residual is not a measured glacier contribution. |
| Where do the risk categories come from? | Prototype screening thresholds, not validated failure probabilities or operating limits. Show the rules and their caveat. |
| Can a data centre or power plant safely use this river? | The app cannot determine that. Historical flow exposure must be combined with demand, temperature/quality, permits, intake/storage and alternatives. |
| Is the 3D display a prediction? | No. Flow surfaces visualize saved historical records; the risk point summarizes historical diagnostics. Prediction modules are unfinished. |
| Would your headline survive another baseline or end year? | This has not yet been demonstrated. Prepare a small sensitivity table, including completeness and influential-year choices. |
| Could a product update look like environmental change? | Yes. NASA documents a 2025 forcing change; its effect here remains unquantified. Version and breakpoint sensitivity belong in validation. |
| Can you reproduce the exact graph on my computer? | Not yet demonstrated independently. Code, sources and settings exist, but frozen manifests, dependencies, access and data preparation need a rehearsed path. |
| Does it work without Wi-Fi? | Saved charts, tables and river geometry do; satellite/reference tiles need network. Prepare the demonstration accordingly. |
| Can it handle all European rivers and many users? | That has not been tested. Current full-frame scans, in-memory tables and per-request calculation are local-prototype bottlenecks. |
| Do passing tests prove the science? | No. They establish selected software behaviors. Data validity, method assumptions, robustness and operational usefulness require separate evidence. |
| What would you do next? | Correct provenance/calendar defects, validate a few headline cases, freeze a reproducible build and test a specific user decision. Scaling and calibrated risk follow those foundations. |

## Recommended work order

1. **Protect the claims now.** Present this as historical exploration; identify modeled inputs, exploratory associations and uncalibrated screening. Do not imply forecasts, causal attribution or safe operating decisions. Choose one concrete user story and a few results that can be checked independently.
2. **Correct known scientific defects before relying on affected quantities.** Preserve provider flags; regularize calendars; enforce continuity; fix GLDAS interval assignment; align leap days; handle source-specific SWE resets. Regenerate affected outputs with preserved old versions and quantify changes.
3. **Validate the results, not just the functions.** Manually reproduce a small representative set of Swiss/Norwegian annual and seasonal metrics from raw records. Include a glacier-influenced basin, a small basin dominated by one GLDAS cell and a record with gaps. Check spatial/time support and provider quality.
4. **Build a sensitivity sheet for every pitch headline.** Report effect size, sample years, coverage and uncertainty across reasonable periods, baselines, interpolation/quality policies and dependence assumptions. Show failures or reversals rather than hiding them.
5. **Freeze and rehearse delivery.** Record code SHA, dependency versions, source versions/checksums, actual intervals and output hashes. Finish data builds before the demo. Test judge access signed out and reproduce the selected graphs on a second environment. Resolve current-document contradictions and source/license records.
6. **Remove measured bottlenecks without renovating the UI.** Cache metadata/options, load lazily, paginate tables on the server, stream exports, version static assets and publish builds atomically. Retain the existing visual design and interaction behavior.
7. **Only then broaden the product.** Gather real user requirements, calibrate decision rules against outcomes, evaluate spatial/temporal generalization and establish deployment requirements. A physics/forecast model is a separate scientific project, not a missing decorative feature.

## Checks and review limits

- Repository status and commit were inspected; main was clean at review start. The report is the only intended tracked change from this task.
- Read-only probes covered saved completeness, date continuity, timing, window support, provider correction counts and GLDAS cell weights, plus synthetic boundary examples and local latency/payload measurements.
- Full Python suite: **124 passed, 1 warning in 438.11 seconds** using the project's `.venv`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `python -m pytest --basetemp=tmp/pytest-project-review-20261115 -q`. The warning is SciPy `ConstantInputWarning` from the synthetic combined-station fixture at `plots.py:691`: correlation is undefined for a constant input. It is not a failed test. Passing this suite does not invalidate the separately reproduced scientific defects above.
- `node tests/risk_assessment/risk-rules.test.mjs`: passed screening-boundary, missingness, role and surface assertions.
- Packaging source-manifest inspection completed; wheel execution was blocked by missing local `bdist_wheel`. No dependency was downloaded for that check.
- No new observation downloads, complete reprocessing, live-provider refresh, load test or browser interaction run was performed for this audit. Earlier integration browser checks remain historical evidence in [the handoff](ui-mechanics-integration.md).
- A polygon-area/sample-distribution probe was interrupted without a result; no conclusion here relies on it. The measured frame-memory estimate is not process RAM. Current GLDAS coverage loss and corrected annual-trend impact remain unquantified.
- This report was prepared with OpenAI Codex assistance using parallel scientific, source and software reviews. Source links document provider/method details; the team must review scientific conclusions and decide changes. No model version is asserted where it was not recorded.
