"""Historical river-flow diagnostics, not forecasts or service-failure estimates."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import theilslopes

MIN_YEARS = 15
MIN_BASELINE_YEARS = 10


def daily_record(frame):
    """Regular daily index; exclude invalid and explicitly interpolated values."""
    if frame.empty:
        raise ValueError("No daily discharge for this gauge.")
    d = frame.copy()
    d["date"] = pd.to_datetime(d["date"])
    if d.date.dt.tz is not None:
        d["date"] = d.date.dt.tz_localize(None)
    if not d.date.eq(d.date.dt.normalize()).all() or d.date.duplicated().any():
        raise ValueError("Expected unique daily dates, without time-of-day components.")
    d = d.set_index("date").sort_index()
    q = pd.to_numeric(d["discharge_vol"], errors="coerce")
    q = q.where(np.isfinite(q) & (q >= 0))
    flag = "discharge_vol_filled"
    excluded = int(d[flag].fillna(False).astype(bool).sum()) if flag in d else 0
    if flag in d:
        q = q.mask(d[flag].fillna(False).astype(bool))
    q = q.reindex(pd.date_range(q.index.min(), q.index.max(), freq="D"))
    return q, excluded, flag in d


def year_dates(year, start_month):
    start = pd.Timestamp(year=year if start_month == 1 else year - 1, month=start_month, day=1)
    return pd.date_range(start, start + pd.DateOffset(years=1) - pd.Timedelta(days=1), freq="D")


def annual_metrics(q, months, start_month):
    years = range(q.index.min().year, q.index.max().year + 2)
    rows = []
    for year in years:
        dates = year_dates(year, start_month)
        if dates[-1] < q.index.min() or dates[0] > q.index.max():
            continue
        values = q.reindex(dates)
        season = values[values.index.month.isin(months)]
        complete = season.notna().all()
        volume = float(season.sum() * 86400) if complete else np.nan
        half = np.nan
        if values.notna().all() and values.sum() > 0:
            half = float(np.searchsorted(values.cumsum().to_numpy(), values.sum() / 2) + 1)
        rows.append(dict(year=year, volume_m3=volume, half_volume_day=half,
                         valid_season_days=int(season.notna().sum()), expected_season_days=len(season)))
    return pd.DataFrame(rows)


def fit(years, values):
    good = np.isfinite(values)
    if good.sum() < MIN_YEARS:
        return None
    x, y = np.asarray(years)[good], np.asarray(values)[good]
    slope, intercept, _, _ = theilslopes(y, x, method="joint")
    return dict(slope=float(slope), intercept=float(intercept), n=int(len(x)))


def threshold_events(q, requirement):
    """Missing dates and analysis boundaries censor episodes; never bridge gaps."""
    q = q.reindex(pd.date_range(q.index.min(), q.index.max(), freq="D"))
    valid = q.notna()
    below = valid & (q < requirement)
    events, run = [], []
    def finish(end_index):
        if not run:
            return
        first, last = run[0], run[-1]
        left = first == 0 or not valid.iloc[first - 1]
        right = end_index == len(q) or not valid.iloc[end_index]
        segment = q.iloc[run]
        events.append(dict(start=str(segment.index[0].date()), end=str(segment.index[-1].date()),
                           days=len(run), deficit_m3=float(((requirement - segment) * 86400).sum()),
                           censored=bool(left or right)))
        run.clear()
    for i, is_below in enumerate(below):
        if is_below:
            run.append(i)
        else:
            finish(i)
    finish(len(q))
    durations = [e["days"] for e in events if not e["censored"]]
    return dict(valid_days=int(valid.sum()), missing_days=int((~valid).sum()),
                below_days=int(below.sum()), below_percent=float(100 * below.sum() / valid.sum()) if valid.any() else None,
                observed_segments=len(events), complete_events=len(durations),
                longest_observed_segment_days=max((e["days"] for e in events), default=0),
                median_complete_duration_days=float(np.median(durations)) if durations else None,
                deficit_m3=float(((requirement - q).clip(lower=0) * 86400).sum()) if valid.any() else None,
                above_requirement_m3=float(((q - requirement).clip(lower=0) * 86400).sum()) if valid.any() else None,
                events=events)


def assess(frame, *, months=(8, 9), start_month=10, period=(1982, 2020), baseline=(1982, 2001), requirement=None):
    months = sorted(set(months))
    if not months or any(m not in range(1, 13) for m in months):
        raise ValueError("Choose month numbers from 1 to 12.")
    if start_month not in range(1, 13):
        raise ValueError("Invalid hydrological-year start month.")
    for first, last in (period, baseline):
        if not 1800 <= first <= last <= 2200:
            raise ValueError("Year ranges must be ordered and between 1800 and 2200.")
    if requirement is not None and (not np.isfinite(requirement) or requirement < 0):
        raise ValueError("Requirement must be a finite non-negative daily flow in m3/s.")
    q, excluded, flags = daily_record(frame)
    annual = annual_metrics(q, months, start_month)
    base = annual[annual.year.between(*baseline)].dropna(subset=["volume_m3"])
    selected = annual[annual.year.between(*period)].copy()
    if selected.empty:
        raise ValueError("The analysis period does not overlap the saved record.")
    # A single point uses the same years on all three axes.
    common = selected.dropna(subset=["volume_m3", "half_volume_day"])
    b = float(base.volume_m3.mean()) if len(base) >= MIN_BASELINE_YEARS else None
    xfit = fit(common.year.to_numpy(), common.volume_m3.to_numpy())
    yfit = fit(common.year.to_numpy(), common.half_volume_day.to_numpy())
    warnings = ["Historical diagnostics, not a forecast or operational risk score.",
                "X and Z use selected months; Y uses the whole hydrological year.",
                "Slopes are descriptive. No significance test or dependence-aware confidence interval is provided.",
                "Provider quality codes are retained upstream but not additionally filtered here; review them before decisions."]
    if excluded:
        warnings.append(f"Excluded {excluded} flagged interpolated days from the saved gauge record.")
    if not flags:
        warnings.append("Interpolation provenance is unavailable; unflagged saved values are used as supplied.")
    if len(common) < MIN_YEARS:
        warnings.append(f"XYZ needs at least {MIN_YEARS} common complete years; found {len(common)}.")
    if b is None:
        warnings.append(f"Baseline needs at least {MIN_BASELINE_YEARS} complete seasons; found {len(base)}.")
    if b is not None and b <= 0:
        warnings.append("Zero baseline: normalized quantity and variability are undefined.")
    ready = xfit is not None and yfit is not None and b is not None and b > 0
    xyz = dict(quantity_pct_decade=1000 * xfit["slope"] / b if ready else None,
               timing_days_decade=10 * yfit["slope"] if yfit else None,
               variability_pct_baseline=100 * float(common.volume_m3.std(ddof=1)) / b if ready else None)
    dates = pd.date_range(year_dates(period[0], start_month)[0], year_dates(period[1], start_month)[-1])
    flow = q.reindex(dates)
    by = flow.index.year + ((flow.index.month >= start_month).astype(int) if start_month != 1 else 0)
    historical = q[(q.index >= year_dates(baseline[0], start_month)[0]) & (q.index <= year_dates(baseline[1], start_month)[-1])]
    groups = historical.groupby(historical.index.strftime("%m-%d"))
    band = groups.quantile([.1, .5, .9]).unstack().reindex(columns=[.1, .5, .9])
    counts = groups.count()
    band.loc[counts < MIN_BASELINE_YEARS, :] = np.nan
    seasonal_flow = flow.where(flow.index.month.isin(months))
    events = threshold_events(seasonal_flow, requirement) if requirement is not None else None
    if events:
        events["missing_days"] = int((flow.index.month.isin(months) & flow.isna()).sum())
        events["excluded_nonseason_days"] = int((~flow.index.month.isin(months)).sum())
    annual_exposure = []
    if requirement is not None:
        for year in selected.year:
            segment = seasonal_flow[by == year]
            summary = threshold_events(segment, requirement)
            annual_exposure.append(dict(year=int(year), below_percent=summary["below_percent"], deficit_m3=summary["deficit_m3"]))
        warnings += ["Present-day constant threshold applied to historical flow: scenario exposure, not unmet demand.",
                     "Deficits cover valid selected-season days only; missing days are not zero. Season boundaries censor episodes.",
                     "Above-requirement volume is not flood risk. Storage, allocations and usable supply are not modelled."]
    latest = int(selected.year.max())
    display = q.reindex(year_dates(latest, start_month))
    keys = display.index.strftime("%m-%d")
    hydrograph = dict(dates=display.index.strftime("%Y-%m-%d").tolist(), flow=display.tolist(),
                     low=band[.1].reindex(keys).tolist(), median=band[.5].reindex(keys).tolist(), high=band[.9].reindex(keys).tolist(),
                     requirement=[requirement if d.month in months else None for d in display.index])
    return dict(xyz=xyz, xyz_ready=ready, baseline_volume_m3=b, baseline_years=len(base), common_years=len(common),
                common_year_labels=common.year.tolist(), annual=selected.to_dict("records"), fits=dict(volume=xfit, timing=yfit),
                hydrograph=hydrograph, display_year=latest, exposure=events, annual_exposure=annual_exposure,
                settings=dict(months=months, period=list(period), baseline=list(baseline), hydro_year_start_month=start_month,
                              requirement_m3s=requirement, min_years=MIN_YEARS, min_baseline_years=MIN_BASELINE_YEARS),
                warnings=warnings)
