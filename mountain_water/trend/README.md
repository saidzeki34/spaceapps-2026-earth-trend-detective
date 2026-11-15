# trend: CAMELS-CH water availability trends

This folder downloads CAMELS-CH, parses the **observed daily series**, selects mountain headwater catchments, and computes how much water flows and when. It then tests for trends, compares 10-year windows, relates flow to its possible drivers and builds Plotly figures. Switzerland only for now. No NASA data and no forecasts yet.

## Run

```text
uv pip install -e ".[dev]"                     # or: pip install -e ".[dev]"
python -m mountain_water.trend download        # Zenodo -> data/raw/camels_ch/v<version>/ (md5-checked, ~250 MB)
python -m mountain_water.trend inspect         # check real columns against the assumptions below
python -m mountain_water.trend build           # -> data/processed/trend/*.parquet
python -m mountain_water.trend report --gauge <id>   # -> data/exports/trend/*.html + *.csv
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

## Assumptions to verify on the real download

The code was developed **without access to the real files**. It was tested only on a synthetic dataset with the documented CAMELS-CH layout (`tests/trend/conftest.py`). After `download`, run `inspect` and check:

- observed files and header names: `discharge_vol(m3/s)`, `discharge_spec(mm/d)`, `precipitation(mm/d)`, `temperature_mean(degC)`, `swe(mm)`, `rel_sun_dur(%)`
- attribute names used by the filter and labels: `elev_mean`, `area`, `num_reservoir` (any of the candidates in `settings.py`), `gauge_name`, `gauge_lat`, `gauge_lon`

If a filter column is missing, the build log shows `SKIPPED` for that step. Add the real name to the candidates in `settings.py`.

## Interpretation limits

Correlations and the attribution describe **statistical association**, not proven cause. Glacier storage, hydropower regulation and measurement changes can all contribute. Missing observations stay NaN and never become zero. Scientific claims need human review before they are presented.
