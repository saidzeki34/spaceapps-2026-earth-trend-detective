# trend: CAMELS-CH water availability trends

This folder downloads CAMELS-CH, parses the **observed daily series**, selects mountain headwater catchments, and computes how much water flows and when. It then tests for trends, compares 10-year windows, relates flow to its possible drivers and builds Plotly figures. Switzerland only for now. No NASA data and no forecasts yet.

## Run

```text
uv pip install -e ".[dev]"                     # or: pip install -e ".[dev]"
python -m mountain_water.trend download        # Zenodo -> data/raw/camels_ch/v<version>/ (md5-checked, ~250 MB)
python -m mountain_water.trend inspect         # list files, columns and units of the download
python -m mountain_water.trend build           # -> data/processed/trend/*.parquet
python -m mountain_water.trend report --gauge 2268 --gauge 2327   # -> data/exports/trend/*.html + *.csv
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

## Interpretation limits

Correlations and the attribution describe **statistical association**, not proven cause. Glacier storage, hydropower regulation and measurement changes can all contribute. Missing observations stay NaN and never become zero. Scientific claims need human review before they are presented.
