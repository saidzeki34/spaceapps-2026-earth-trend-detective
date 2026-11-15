"""Possible drivers of flow change: annual climate/snow aggregates, correlations and a simple attribution.

Everything here describes statistical association in observations. It does not prove causation;
shared long-term trends, regulation and glacier storage can all produce correlations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .trends import sen_slope

WINTER_MONTHS = (10, 11, 12, 1, 2, 3)


def _swe_dates(doy: np.ndarray, swe: np.ndarray) -> tuple[float, float]:
    if np.isnan(swe).all() or np.nanmax(swe) <= 0:
        return np.nan, np.nan
    i_peak = int(np.nanargmax(swe))
    peak = swe[i_peak]
    after = np.where(swe[i_peak:] <= 0.05 * peak)[0]
    meltout = float(doy[i_peak + after[0]]) if len(after) else np.nan
    return float(doy[i_peak]), meltout


def annual_driver_metrics(daily: pd.DataFrame) -> pd.DataFrame:
    """Annual aggregates of the observed meteorological series that exist in ``daily``."""
    df = daily.copy()
    month = df["date"].dt.month
    g = df.groupby(["gauge_id", "hydro_year"])
    out = pd.DataFrame(index=g.size().index)

    if "precipitation" in df:
        out["precip_total_mm"] = g["precipitation"].sum(min_count=300)
        out["precip_winter_mm"] = df[month.isin(WINTER_MONTHS)].groupby(["gauge_id", "hydro_year"])["precipitation"].sum(min_count=150)
        out["precip_summer_mm"] = df[~month.isin(WINTER_MONTHS)].groupby(["gauge_id", "hydro_year"])["precipitation"].sum(min_count=150)
    if "temperature_mean" in df:
        out["temp_mean"] = g["temperature_mean"].mean()
        out["temp_spring"] = df[month.isin((3, 4, 5))].groupby(["gauge_id", "hydro_year"])["temperature_mean"].mean()
        out["temp_summer"] = df[month.isin((6, 7, 8))].groupby(["gauge_id", "hydro_year"])["temperature_mean"].mean()
        if "precipitation" in df:
            snow = df["precipitation"].where(df["temperature_mean"] <= 0, 0.0)
            out["snowfall_frac"] = df.assign(_snow=snow).groupby(["gauge_id", "hydro_year"])["_snow"].sum() / out["precip_total_mm"]
    if "swe" in df:
        # SWE coverage can be shorter than the flow record; only use (nearly) complete years.
        complete = g["swe"].count() >= 330
        out["swe_max_mm"] = g["swe"].max().where(complete)
        dates = {
            key: _swe_dates(grp["hydro_doy"].to_numpy(), grp["swe"].to_numpy(dtype=float))
            for key, grp in df.sort_values("date").groupby(["gauge_id", "hydro_year"])
        }
        out["swe_peak_doy"] = pd.Series({k: v[0] for k, v in dates.items()}).where(complete)
        out["swe_meltout_doy"] = pd.Series({k: v[1] for k, v in dates.items()}).where(complete)
    if "rel_sun_dur" in df:
        out["sun_mean_pct"] = g["rel_sun_dur"].mean()
    return out.reset_index()


def _detrend(years: np.ndarray, values: np.ndarray) -> np.ndarray:
    ok = np.isfinite(values)
    if ok.sum() < 3:
        return values
    slope, intercept = np.polyfit(years[ok], values[ok], 1)
    return values - (slope * years + intercept)


def correlations(
    annual: pd.DataFrame,
    targets: list[str],
    drivers: list[str],
    method: str = "spearman",
    detrend: bool = True,
    min_years: int = 15,
) -> pd.DataFrame:
    """Per-gauge correlation of each flow metric with each driver across years.

    ``detrend=True`` removes linear trends first so that two variables that merely both change
    over time are not reported as related (year-to-year co-variation only).
    """
    corr = stats.spearmanr if method == "spearman" else stats.pearsonr
    rows = []
    for gauge_id, grp in annual.groupby("gauge_id"):
        years = grp["hydro_year"].to_numpy(dtype=float)
        for t in targets:
            if t not in grp:
                continue
            y = grp[t].to_numpy(dtype=float)
            y = _detrend(years, y) if detrend else y
            for d in drivers:
                if d not in grp or d == t:
                    continue
                x = grp[d].to_numpy(dtype=float)
                x = _detrend(years, x) if detrend else x
                ok = np.isfinite(x) & np.isfinite(y)
                if ok.sum() < min_years or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
                    continue
                r, p = corr(x[ok], y[ok])
                rows.append(dict(gauge_id=gauge_id, metric=t, driver=d, r=float(r), p=float(p), n=int(ok.sum())))
    return pd.DataFrame(rows, columns=["gauge_id", "metric", "driver", "r", "p", "n"])


def correlation_summary(corr: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Across catchments: median correlation and share of catchments with a significant relation."""
    g = corr.assign(sig=corr["p"] < alpha).groupby(["metric", "driver"])
    return g.agg(median_r=("r", "median"), share_significant=("sig", "mean"), n_catchments=("r", "size")).reset_index()


def attribute_change(
    annual: pd.DataFrame,
    flow: str = "runoff_mm",
    precip: str = "precip_total_mm",
    temp: str = "temp_mean",
    min_years: int = 15,
) -> pd.DataFrame:
    """Split the observed flow trend into a precipitation part, a temperature part and a residual.

    Per catchment, year-to-year relative flow anomalies are regressed on relative precipitation
    anomalies and temperature anomalies (dQ/Q = a·dP/P + b·dT). ``a`` is the precipitation
    elasticity and ``b`` the temperature sensitivity (fraction per °C). Multiplying these with the
    Sen slopes of the drivers gives the expected flow change per decade from each driver. The
    residual collects everything else (glacier storage change, land use, regulation, errors).
    """
    rows = []
    for gauge_id, grp in annual.groupby("gauge_id"):
        cols = [flow, precip, temp]
        if any(c not in grp for c in cols):
            continue
        d = grp[["hydro_year", *cols]].dropna()
        if len(d) < min_years:
            continue
        q, p, t = (d[c].to_numpy(dtype=float) for c in cols)
        qm, pm, tm = q.mean(), p.mean(), t.mean()
        X = np.column_stack([(p - pm) / pm, t - tm, np.ones(len(d))])
        coef, *_ = np.linalg.lstsq(X, (q - qm) / qm, rcond=None)
        fitted = X @ coef
        resid = (q - qm) / qm - fitted
        r2 = 1 - resid.var() / ((q - qm) / qm).var()
        years = d["hydro_year"].to_numpy(dtype=float)
        sq, sp, st = (sen_slope(years, v)[0] * 10 for v in (q, p, t))
        from_p = coef[0] * qm * sp / pm
        from_t = coef[1] * qm * st
        rows.append(dict(
            gauge_id=gauge_id, n_years=len(d), mean_flow=qm,
            precip_elasticity=coef[0], temp_sensitivity_per_degC=coef[1], r2=r2,
            observed_change_per_decade=sq, from_precip_per_decade=from_p, from_temp_per_decade=from_t,
            residual_per_decade=sq - from_p - from_t,
        ))
    return pd.DataFrame(rows)
