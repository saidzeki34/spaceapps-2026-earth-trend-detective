# Methods and interpretation

This document describes the implemented foundation, not a claim that its scientific choices have received team review. Preserve the exact source/version, quality policy, calendar, region, selected dates and requirement in every interpretation. Human scientific review remains required.

## Discharge, volume and missingness

Discharge `Q` is an interval-average rate in m³/s. An accepted interval of duration `dt` seconds contributes `Q × dt` m³. Invalid or missing values do not contribute zero: they are excluded, reduce coverage and can make a total unavailable.

The application exposes observed subtotal, assessed duration and expected duration. A complete-period total is available only when all expected duration is covered by valid intervals. The calendar summaries require aligned full 24-hour daily means. Instantaneous samples have no implicit integration rule and are rejected. Daily p10/p90 values summarize valid daily means; they do not describe subdaily extremes.

## Historical baseline

Reference years are independent of analysis years and the requirement. Valid reference observations are grouped by calendar month/day. Each group retains mean, median, empirical 10th and 90th percentiles, accepted count, expected count and completeness. February 29 has its own group; a non-leap observation is not moved or duplicated to fill it.

The plotted band is a historical distribution, not a confidence or prediction interval. Low sample counts and changing coverage remain visible. No imputation makes the reference record appear complete.

## Seasonal totals and timing

A water year starts in the selected month and is labelled by its **starting calendar year**. For example, October 2019 through September 2020 is labelled 2019. Seasonal quantity sums only selected calendar months within that water year. A seasonal total requires every selected day to be valid; an annual total requires every day in the water year. Incomplete periods retain coverage but have missing totals and are excluded from trend fits.

Timing is the elapsed day from the water-year start when cumulative annual volume reaches half the complete annual volume. The crossing is linearly located within the daily interval, explicitly assuming that day's mean flow is constant. A partial annual record or an all-zero annual volume has no defined half-volume timing. This timing metric does not measure a flood peak or the onset of snowmelt.

## Requirement exposure

For an assessable flow interval with supply-rate observation `S` and threshold `R`:

- Deficit volume: `max(R - S, 0) × dt` in m³.
- Margin volume: `max(S - R, 0) × dt` in m³.
- Below-threshold fraction: assessed duration with `S < R`, divided by all assessed duration.
- Adequacy fraction: assessed duration with `S >= R`, divided by all assessed duration.

Equality meets the threshold. Expected duration remains a separate denominator for reporting coverage. Missing flow, a missing requirement, or a requirement changing within a coarse mean interval makes that interval unresolved. The application does not use a baseline as demand or infer finer flow variation from a daily/monthly mean.

An event is a consecutive run of below-threshold native intervals. A gap, invalid value or analysis boundary censors a run; event records retain censored start/end flags. Durations describe observed interval-average runs, not continuous intraday shortages. Monthly forecast exposure withholds event count and duration because monthly means cannot resolve daily events.

These are river-flow threshold calculations. They are not reservoir simulation, delivered supply, shortage probabilities or a universal service-risk score. Historical discharge can include regulation; future operations, abstractions and user resilience are not established by the station series.

## Three comparison axes

Let `B` be the mean of complete seasonal reference-year volumes, `bQ` the fitted seasonal-volume slope in m³/year, `bT` the half-volume timing slope in days/year and `s` the sample standard deviation (`ddof=1`) of detrended seasonal-volume residuals.

| Axis | Calculation | Interpretation |
| --- | --- | --- |
| Quantity | `100 × 10 × bQ / B` | Percent of a fixed reference volume per decade |
| Timing | `10 × bT` | Days per decade; negative means earlier half-volume passage |
| Variability | `100 × s / B` | Detrended annual scatter as percent of the fixed reference volume |

`B` must be finite and positive; near-zero baselines can produce unstable normalized values and need review. At least three complete values are required to fit a descriptive slope. Residual SD is not residual standard error and is not a trend in variability. No combined risk score is formed.

The same point appears in a 3D view and a 2D view. Hover/table metadata retains outlet, windows, season, sample count, coverage, uncertainty status and regulation. Only matching analysis/reference windows, seasons and water-year definitions are intended for comparison; source calendar, regulation and quality differences still need review.

## Trend uncertainty and multiple comparisons

OLS fits one complete-period value per actual water-year coordinate. Missing years are not compressed into consecutive indices. Fewer than three complete values yields no slope. A descriptive slope can be reported with fewer than twenty complete years, but the uncertainty state remains `insufficient_evidence`.

The exploratory interval requires at least twenty **consecutive** complete years. It resamples contiguous residual blocks of length `ceil(n^(1/3))`, at least two years, using 1,999 replicates and seed 2026. Individual intervals use the 1.25th and 98.75th percentiles (97.5%) for two planned slopes within one assessment. This Bonferroni adjustment does not cover repeated searches across outlets, seasons, variables or user-selected windows.

Residual block resampling is motivated by dependent-observation bootstrap methods; see [Künsch (1989)](https://doi.org/10.1214/aos/1176347265). This particular implementation and eligibility rule do not guarantee interval coverage. Short-range, approximately stationary residual dependence is an assumption; strong persistence, structural changes, heteroskedasticity and baseline uncertainty can invalidate simple interpretation. No independence-assuming daily p-value is reported. An interval excluding zero is exploratory evidence conditional on these choices, not proof of a mechanism or causality.

## Provider transformations and NASA context

NVE HydAPI parameter 1001 is requested as daily mean discharge. The implementation accepts quality codes 2/3 and correction codes 0/1/4/11, preserves native codes/raw values, and rejects other observations from analysis. This is a versioned project screening choice requiring review against [NVE documentation](https://hydapi.nve.no/UserDocumentation/), not an assertion that all rejected values are physically wrong. Daily 11:00 UTC labels are mapped to fixed-CET midnight intervals by subtracting twelve hours.

Swiss flow is the CAMELS-CH v0.9 observation-based `discharge_vol(m3/s)` series. The pinned archive covers 1981–2020 and lacks per-observation quality flags in that table. Finite nonnegative values are accepted, with this limitation retained. Date labels are nominal 24-hour UTC intervals; precise subdaily timing is not established. The [CAMELS-CH publication](https://doi.org/10.5194/essd-15-5755-2023) and [pinned archive](https://zenodo.org/records/15025258) identify the source. Ice and historical management remain interpretation limits.

The NASA route uses [MODIS/061/MOD10A1](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1), band `NDSI_Snow_Cover`, at its native nominal 500 m grid. It accepts index values 0–100 and Basic QA 0/1, requiring Algorithm Flags QA bits 0, 1, 2, 3, 4 and 7 to be clear. The area-weighted index mean uses accepted pixel intersection area; coverage divides accepted area by total catchment raster area. The native grid/projection is retained rather than selecting a coarser resolution to complete a request.

Means below **50% valid area** are withheld. This is the project's coverage rule, not a NASA accuracy guarantee. Clouds and conservative screening can change which pixels are represented; the accepted mean can shift because coverage changes. The interface therefore plots coverage alongside index and flow. Missing imagery retains a missing index.

The index is **not fractional snow-covered area**, as explained by [NSIDC](https://nsidc.org/data/user-resources/help-center/what-ndsi-snow-cover-and-how-does-it-compare-fsc). It is also not snow-water equivalent or available river-water volume. A daily composite label is not a synchronous observation with outlet discharge. Time-aligned plots provide environmental context; they establish neither a causal explanation nor a validated snow-to-flow model.

## Outlook and hindcasts

The available model repeats historical complete calendar-month means. It requires at least three complete historical observations for each of twelve calendar months, and uses only intervals ending by the issue date. It predicts twelve full months beginning with the issue month if issued exactly at that month's start, otherwise the next month. The status is `baseline_only`; p10/p90 shows historical variability, not calibrated forecast uncertainty. Old training data produce a stale-history warning.

Hindcasts use expanding training windows at the last up to five eligible January issue dates, after at least five initial calendar years. Each fit receives only pre-issue observations, including preprocessing. Exact monthly intervals are matched to complete observed months. MAE, RMSE and bias are in m³/s; month-specific scores and assessed coverage are retained. The seasonal baseline is also reported as a benchmark. No future weather or observed future drivers enter training.

The team's equation remains `unavailable` until its formula, parameters, units, storage/routing boundaries, future-driver scenarios and management assumptions are supplied. It must undergo chronological validation before claims of improvement. The current baseline does not model changing climate, glaciers, reservoir operations or abstraction. Monthly threshold exposure is a scenario calculation at monthly resolution, not a shortage forecast.
