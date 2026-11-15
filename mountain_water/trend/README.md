# trend: CAMELS-CH water availability trends

This folder downloads CAMELS-CH, parses the **observed daily series**, selects mountain headwater catchments, and computes how much water flows and when. It then tests for trends, compares 10-year windows, relates flow to its possible drivers and builds Plotly figures. The same analysis runs on **Norwegian NVE** observations (see [Norway](#norway-nve--senorge)) and on **NASA GLDAS-2.1** model output for either country's catchments (see [GLDAS](#gldas-21-noah-nasa)), so observations and the NASA model can be compared. No forecasts yet.

## Run

```text
uv pip install -e ".[dev]"                     # or: pip install -e ".[dev]"
python -m mountain_water.trend download        # Zenodo -> data/raw/camels_ch/v<version>/ (md5-checked, ~250 MB)
python -m mountain_water.trend inspect         # list files, columns and units of the download
python -m mountain_water.trend build           # -> data/processed/trend/*.parquet
python -m mountain_water.trend report --gauge 2268 --gauge 2327   # -> data/exports/trend/*.html + *.csv
python -m mountain_water.trend stations        # station x month heatmap, CH + NO -> data/exports/trend_stations
python -m pytest                               # synthetic CAMELS-CH-shaped fixture
```

`build` options: `--min-elevation 1500 --max-area 500 --max-reservoirs 0 --min-years 30 --window-years 10 --hydro-year-start 10`.

From Python or Streamlit:

```python
from mountain_water.trend import pipeline, plots
r = pipeline.load()                        # TrendResults (tables) from data/processed/trend
plots.regime_by_window(r, r.gauges[0])     # plotly Figure
```

## Pipeline

| Step | Module | What it does |
| --- | --- | --- |
| Download / parse | `camels_ch.py` | Zenodo API (latest version of the CAMELS-CH record), md5 check, extract. Reads `timeseries/observation_based/CAMELS_CH_obs_based_<id>.csv` (units are taken from the headers) and merges every per-gauge `static_attributes/*attributes*.csv`. |
| Prepare / filter | `preprocessing.py`, `settings.py` | Hydrological year Oct–Sep, labelled by its end year. Gaps of 5 days or less are interpolated and flagged; a year counts as valid if at least 90 % of its days were observed. The mountain filter: mean elevation ≥ 1500 m, area ≤ 500 km², no reservoirs, ≥ 30 valid years. |
| How much | `flow_metrics.py` | Mean flow, runoff (mm), volume (hm³), winter/summer flow, Q95, 7-day minimum, Q10, peak, days below the long-term Q347 |
| When | `timing.py` | Centre-of-mass date, half-volume date, peak date, high-flow onset, low-flow date (only in years without remaining gaps) |
| Variability | `variability.py` | Daily-flow CV and Richards-Baker flashiness per year |
| Drivers | `drivers.py` | Annual precipitation (total/winter/summer), snowfall fraction, temperatures, peak SWE and melt-out date, sunshine, runoff ratio. Spearman correlations on detrended values, plus a precipitation/temperature attribution of the runoff trend |
| Long-term trend | `trends.py` | Sen's slope per decade and a Mann-Kendall test with trend-free pre-whitening, Benjamini-Hochberg FDR per metric |
| 10-year windows | `comparison.py`, `seasonal.py`, `baseline.py` | Window means compared with the first window and the previous one (Mann-Whitney U). Seasonal regime per window. Day-of-year percentile bands to compare one year with history. Trends set against catchment attributes |
| Figures | `plots.py`, `registry.py` | 13 Plotly figure functions (light/dark) plus a monthly-regime table, built from the tables in `TrendResults` |

The 10-year windows start at the first valid hydrological year, 1982 (Oct 1981–Sep 1982), because the record starts in January 1981. That gives 1982–1991, 1992–2001, 2002–2011 and 2012–2020. A final window shorter than 8 years is dropped. Use `--hydro-year-start 1` to get calendar-year decades (1981–1990, ...).

## Norway (NVE + seNorge)

```text
export NVE_API_KEY=<key>                               # free: https://hydapi.nve.no/Users
python -m mountain_water.trend inspect --source nve    # real field names of the three services (check first)
python -m mountain_water.trend -v download --source nve
python -m mountain_water.trend build --source nve      # -> data/processed/trend_no
python -m mountain_water.trend report --source nve --gauge <station id, e.g. 2.11.0>
# NASA comparison for the same Norwegian catchments (needs EARTHDATA_TOKEN):
python -m mountain_water.trend -v download --source gldas --region no
python -m mountain_water.trend build --source gldas --region no      # -> data/processed/trend_no_gldas
python -m mountain_water.trend report --source gldas --region no --gauge <id>
```

| Data | Source | Notes |
| --- | --- | --- |
| Daily discharge | NVE HydAPI, parameter 1001, resolution 1440 | m³/s, dated in Norwegian local time. The quality code is kept. Specific discharge = Q × 86.4 / area |
| Station metadata | HydAPI `/Stations` | `drainageBasinArea`, `heightHypso50` (median elevation), `percentGlacier`, `catchmentRegTypeName` plus the reservoir fields, and the daily-discharge period from `seriesList` (field names verified 2026-11-15) |
| Catchment outlines | NVE map service `HydrologiskeData3`, layer 38 "Totalnedbørfelt til målestasjon" (EPSG:25833) | Matched to stations on (watercourse area, station number) from `stasjonnr` or `compoundkey12`, whichever matches more stations. Version suffix and zero padding are ignored (`2.11`, `2.11.0` and `002.00011.000` are the same station) |
| Precipitation, temperature, SWE | seNorge 1 km grids via NVE GridTimeSeries point series (`GridTimeSeries/{x}/{y}/{start}/{end}/{theme}.json`), themes `rr`, `tm`, `swe` | Each catchment is sampled on a regular grid of 1 km cell centres (about 20 points; every cell in small catchments) and the points are averaged. One request per point and theme covers the whole period (about 0.6 s each). No key needed. The polygon endpoint (`AggregationTimeSeries/ByGeoJson`) returned HTTP 500 for every request on 2026-11-15, including NVE's own example |

**Filter** (`TrendSettings.nve()`): median catchment elevation ≥ 800 m, area ≤ 500 km², unregulated, ≥ 30 valid years. Regulation follows NVE's category `catchmentRegTypeName`: only categories starting with "uregulert" are kept. Anything else containing "regulert" is excluded, including "regulert m/magasinregulering", "… og overføringer" and "regulert m/magasin og uregulert restfelt". Only stations without a category fall back to the numeric fields (any reservoir count, area or volume > 0 excludes). The category takes precedence because a regulated station can have every numeric regulation field at 0 (e.g. 1.200.0). The download step applies the same metadata filter first, so only candidate stations are fetched.

**Period:** October 1960 to the latest complete hydrological year. Windows: 1961–1970, …, 2011–2020, plus 2021–latest (kept because it has ≥ 5 years). The overlap with GLDAS starts in 2001.

**Checked with `inspect --source nve` on 2026-11-15:**
- HydAPI: 1,904 stations; all station fields above are present.
- Regulation categories: 335 "uregulert", 398 "regulert m/magasinregulering", 335 "… og overføringer", 139 "… og uregulert restfelt", and 697 with no category (numeric fallback).
- Outline layer: `stasjonnr` is written like `76.5.0`.
- seNorge: `rr`, `tm` (°C) and `swe` (mm) are daily from 1957.

**Live run on 2026-11-15:** the whole chain ran on real data.
- Metadata pre-filter: 96 candidate stations; discharge for all 96 downloaded in under a minute; all 96 outlines matched.
- seNorge: 1,125 points × 3 themes (3,375 requests).
- `build --source nve`: 628 stations with daily discharge → 283 at median elevation ≥ 800 m → 167 at ≤ 500 km² → 118 unregulated → **84 catchments** with ≥ 30 valid years. Windows 1961–1970 … 2011–2020 and 2021–2026.
- `build --source gldas --region no`: all 84 catchments, windows 2001–2010, 2011–2020, 2021–2025.

Good gauges to start with: 2.13.0 (Sjoa at Nedre Sjodalsvatn, median 1542 m) and 88.4.0 (Lovatn, 33 % glacier). Candidate names live at the top of `nve.py`. Tests run the whole Norway chain, including GLDAS for Norway, against fake services (`tests/trend/test_nve.py`).

## GLDAS-2.1 Noah (NASA)

GLDAS is NASA's Global Land Data Assimilation System. This pipeline uses **GLDAS_NOAH025_3H 2.1**: the Noah land-surface model on a 0.25° grid, 3-hourly, from 2000 to about 3 months ago. GLDAS is a model, not a measurement. It has no gauges, and its runoff isn't routed down rivers.

```text
export EARTHDATA_TOKEN=<token>     # free Earthdata account: urs.earthdata.nasa.gov -> Generate Token (valid 60 days)
python -m mountain_water.trend build                             # CAMELS-CH first (or build --source nve for Norway)
python -m mountain_water.trend download --source gldas --probe   # one tiny request: checks the token and response format
python -m mountain_water.trend download --source gldas           # ~2,200 cached requests into data/raw/gldas; rerun to resume
python -m mountain_water.trend build --source gldas              # -> data/processed/trend_gldas
python -m mountain_water.trend report --source gldas --gauge 2268   # -> data/exports/trend_gldas, incl. observed vs GLDAS
```

| Step | Module | What it does |
| --- | --- | --- |
| Catchments to grid | `catchment_grid.py` | Overlaps each selected CAMELS-CH catchment outline (`catchment_delineations/CAMELS_CH_catchments.shp`, LV95) with the 0.25° cells. Weight per cell = share of the catchment area. The 33 default catchments touch 45 cells (1–5 each). |
| Download | `gldas.py` | Giovanni Time Series API (`api.giovanni.earthdata.nasa.gov/timeseries`; it replaced Hydrology Data Rods) at each cell centre. 8 variables per cell in 5-year requests, with retries. Raw CSVs are cached so reruns skip finished requests. |
| Daily series | `gldas.py` | Converts 3-hourly values to daily ones (see table). Days with fewer than 8 values become NaN, and the fill value −9999 becomes NaN. Catchment means are area-weighted, renormalised when a cell has no data. |
| Analysis | `pipeline.build_gldas` | Uses the same `analyze()` as CAMELS-CH. Requires ≥ 20 valid years. Windows are 2001–2010, 2011–2020 and 2021–latest; a final window of 5 or more years is kept. |
| Observed vs GLDAS | `sources.py`, `plots.source_*` | Over the common hydrological years (2001–2020): catchment means, bias, year-to-year correlation, trends from both sources and the seasonal hydrograph. |

| GLDAS variable | Column | Daily value |
| --- | --- | --- |
| `Qs_acc` + `Qsb_acc` | `discharge_spec` (plus `runoff_surface`, `runoff_base`) | Total runoff, mm/d. `discharge_vol` = the same converted to m³/s with the catchment area |
| `Qsm_acc` | `snowmelt` | mm/d |
| `Rainf_f_tavg`, `Snowf_tavg` | `precipitation`, `snowfall` | rate × 86400, mm/d |
| `Evap_tavg` | `evap` | rate × 86400, mm/d |
| `Tair_f_inst` | `temperature_mean` | K − 273.15, °C |
| `SWE_inst` | `swe` | mm |

Checked against the live API on 2026-11-15 with `--probe`: the token is accepted and the response parses. It has `key,value` metadata lines including `unit` and `undef`, then `Timestamp (UTC),Data` rows such as `2010-01-01 03:00,259.673`. When the cached data is loaded, each variable's reported `unit` is checked against the unit the conversion assumes (`kg m-2` for `_acc`, `kg m-2 s-1` for `_tavg` rates, `K`, `kg m-2` for SWE). A mismatch stops the build instead of silently producing wrong numbers. The full download hasn't been run yet. Any variable the API refuses is listed in `data/raw/gldas/failed_requests.csv`.

Interpretation: GLDAS runoff isn't routed through river channels, so its timing leads observed discharge. A 0.25° cell is larger than many of these catchments, and glaciers and hydropower aren't represented. Treat GLDAS as consistent model context, and use the comparison with CAMELS-CH to see where it can stand in for observations.

## Verified on the real data

The full pipeline (`download`, `inspect`, `build`, `report`) has been run on **CAMELS-CH v0.9** (Zenodo). It found 331 observed series from 1981-01-01 to 2020-12-31 and every expected header and attribute column. The default filters keep 33 catchments:

| Step | Remaining |
| --- | --- |
| All catchments | 331 |
| Mean elevation ≥ 1500 m (`elev_mean`) | 121 |
| Area ≤ 500 km² (`area`) | 71 |
| No reservoirs (`num_reservoir`) | 53 |
| ≥ 30 years with ≥ 90 % valid flow | 33 |

Good gauges to start with: 2268 (Rhone at Gletsch, glacier-fed), 2327 (Dischmabach, snow-dominated) and 2605 (Verzasca, south of the Alps).

Data notes:
- SWE is missing for about 44 % of catchment-years, so snow metrics cover fewer years than the flow metrics.
- One selected catchment has no temperature series.
- Some catchments still have hydropower plants (`hp_count` > 0), and 2347 is named a compensation basin. Check them before interpreting their trends.

The automated tests (`python -m pytest`) use a small synthetic dataset with the same layout (`tests/trend/conftest.py`), so they run without the download.

## Station × month heatmap

`python -m mountain_water.trend stations` (`stations.py`) shows three things in one figure: **when** in the year flow is changing, **whether the same pattern appears across catchments**, and **whether late-summer losses are larger than the change in annual supply**. It covers Switzerland and Norway in separate panels with the same columns. It has its own selections and uses calendar years, separate from `build`:

- **Switzerland.** CAMELS-CH gauges in Switzerland (`country` CH) on rivers (`water_body_type` stream). Each needs a valid, non-negative discharge on every day of 1981–2020 and some flow in every year. They are ranked by mean catchment elevation (`elev_mean`), and the highest 100 are kept. There is **no reservoir filter**, and some catchments are nested.
- **Norway.** The 84 gauges of the NVE mountain selection from the last `build --source nve` (median elevation ≥ 800 m, ≤ 500 km², unregulated), ranked by median catchment elevation. Discharge comes from the cached HydAPI download in `data/raw/nve`.
- **Complete years.** A calendar year counts only if every day has a valid discharge. No gaps are filled, and the quality code is not filtered. A slope is estimated only for gauges with **≥ 30 complete years, ≥ 10 of them in 1981–2000**. The rest stay in the figure as grey rows and in the tables with empty slopes.
- **Per gauge and complete year:**
  - monthly volume (hm³);
  - August–September volume;
  - annual volume;
  - the lowest 7-day mean flow, counting only 7-day windows that lie entirely within August–September;
  - the half-volume date (the day of the year by which half the year's volume has passed).

  29 February is left out, so every year has 365 days.
- **Per gauge and value:**
  - Sen's slope per decade, as % of the gauge's 1981–2000 mean (the half-volume date in days, negative = earlier);
  - the same slope in **mm of runoff per decade** over the catchment area (mm/d for the 7-day low), because a large % change in a low-flow month can be little water;
  - the Mann-Kendall p-value with trend-free pre-whitening;
  - the Benjamini-Hochberg FDR per column, over all gauges with slopes.

  The colour shows the effect size. ● marks p < 0.05 after FDR, ▲ glacier cover > 0, ■ a recorded reservoir, hydropower plant or regulation.
- **Year anomalies** (`station_year_heatmaps`). Same gauge order, one column per year: August–September volume anomaly and half-volume date anomaly, relative to each gauge's 1981–2000 mean. Grey cells are years without a complete record. It shows whether a slope comes from a gradual shift, a few shared dry years, or an abrupt change at one gauge.
- **Driver scatters** (`driver_change_scatter`). One point per gauge with slopes, one panel per country, coloured by glacier cover. Both values are Sen's slopes fitted over the years where both exist, so differences in record length don't drive the comparison. Two pairs:
  - **Half-volume date against snow-free date.** The snow-free date is the first day after the January–August SWE peak with SWE ≤ 5 % of the peak, from CAMELS-CH or seNorge SWE. Snowpacks with a peak below 10 mm get no date.
  - **Aug–Sep 7-day low against July–September precipitation.** Both are in % of their mean over the fitted years.

  Pairs need ≥ 15 common years. CAMELS-CH SWE starts in 1998, so the Swiss snow comparison covers about 1999–2020.

  Both SWE series drop to ~0 at the start of September; at gauge 2009, for example, SWE goes from 43 mm to 0 between 1 and 2 September 2010. That is a reset, not melt, so only melt-out before 1 September counts. Years with snow left on 31 August get no date, which leaves out most strongly glacierized catchments.

Options: `--region all|ch|no` (default `all`; without an NVE build it falls back to Switzerland), `--n-gauges 100 --period 1981 2020 --baseline 1981 2000 --all-countries`. Outputs in `data/exports/trend_stations`:
- `station_month_heatmap.html`, `station_year_heatmaps.html` and two `driver_*.html` files;
- `station_month_trends.csv` (wide, one row per gauge, % and mm columns, record length) and `station_month_trends_long.csv` (with p-values);
- `station_month_summary.csv` and `station_month_summary_by_infrastructure.csv` (per country and column: counts of negative and positive slopes, and the medians);
- `station_year_anomalies.csv`;
- `station_driver_changes.csv`;
- `station_selection_log.csv`.

**Run on 2026-11-15** (CAMELS-CH v0.9 and the cached NVE download).
- **Switzerland:** 331 catchments → 229 in Switzerland → 196 rivers → 139 complete for 1981–2020 → the 100 highest kept. All 100 have slopes. The lowest has a mean elevation of 986 m. The Swiss selection and values match the exploratory script `plot_station_trends.py` this view was adapted from. The exceptions are February, annual volume and the half-volume date, which differ by at most 1.4 percentage points, 0.2 percentage points and 0.7 days because of leap-day handling.
- **Norway:** 84 gauges, 74 with slopes.
- **Comparison with an exploratory figure made outside the repository:** it covers the same 184 gauges in the same order, and its slopes are identical wherever the complete-year counts agree. That is all 100 Swiss gauges and 48 of the Norwegian ones. For the other Norwegian gauges its NVE data had fewer complete years than our cached download (e.g. 156.19.0: 19 against 26), so it gave slopes for 73 Norwegian gauges instead of 74.

| Value | Switzerland: negative slopes (of 100), median per decade | Norway: positive slopes (of 74), median per decade |
| --- | --- | --- |
| April volume | 50, +0.1 % (−0.0 mm) | 70, +14.6 % (+5.5 mm) |
| July volume | 97, −7.1 % (−8.8 mm) | 25, −1.5 % (−4.2 mm) |
| September volume | 93, −5.3 % (−4.5 mm) | 59, +5.4 % (+6.2 mm) |
| Aug–Sep volume | 87, −3.9 % (−6.3 mm) | 52, +3.9 % (+9.4 mm) |
| Annual volume | 87, −2.4 % (−22.0 mm) | 56, +2.2 % (+27.0 mm) |
| Half-volume date | 74 earlier, −1.1 days | 36 earlier, 28 later, 0.0 days |

- **Unflagged Swiss gauges.** The 42 Swiss gauges without a recorded reservoir or hydropower plant show the same summer pattern: July volume falls at 41, September at 38.
- **Driver scatters, Spearman r across gauges.** Half-volume date against snow-free date: −0.10 for Switzerland (70 gauges, ~1999–2020) and −0.33 for Norway (61 gauges). Aug–Sep 7-day low against July–September precipitation: −0.03 for Switzerland (100 gauges) and +0.22 for Norway (74 gauges).

These are descriptive slopes for two differently selected networks over one period. They are not regional estimates and not attribution. Still open: a second common period, uncertainty intervals that allow for year-to-year dependence, the 10 %/90 % delivery dates, and a MODIS snow-cover check of the snow timing after 2000.

## Interpretation limits

Correlations and the attribution describe **statistical association**, not proven cause. Glacier storage, hydropower regulation and measurement changes can all contribute. Missing observations stay NaN and never become zero. Scientific claims need human review before they are presented.
