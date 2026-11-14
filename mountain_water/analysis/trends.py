"""Descriptive annual slopes with an explicitly qualified block-bootstrap interval."""
import numpy as np


def estimate_trend(years, values, units: str, *, bootstrap_samples=1999) -> dict:
    x, y = np.asarray(years, dtype=float), np.asarray(values, dtype=float)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    result = {"n": len(x), "units": units, "slope_per_year": None, "interval": None,
              "period": [int(x.min()), int(x.max())] if len(x) else None,
              "status": "insufficient_evidence", "method": "OLS on one value per water year",
              "multiple_testing": "Two planned slopes per assessment; 97.5% intervals (Bonferroni).",
              "limitations": "Exploratory; block bootstrap assumes weakly stationary residual dependence. "
              "Short-range dependence, stable variance and a suitable linear trend are assumptions. "
              "Long memory, structural breaks and repeated exploratory searches are not controlled. "
              "Human scientific review required; not causal evidence."}
    if len(x) < 3 or len(np.unique(x)) != len(x):
        return result
    centered = x - x.mean()
    slope = float(centered @ (y - y.mean()) / (centered @ centered))
    if np.all(y == y[0]):
        slope = 0.
    result["slope_per_year"] = slope
    # No independence-assuming daily p-values. Missing years break bootstrap spacing.
    if len(x) < 20 or not np.all(np.diff(x) == 1):
        result["limitations"] += " At least 20 consecutive complete years are required for an interval."
        return result
    residuals = y - (y.mean() + slope * centered)
    block = max(2, int(np.ceil(len(x) ** (1 / 3))))
    rng = np.random.default_rng(2026)
    slopes = np.empty(bootstrap_samples)
    for i in range(bootstrap_samples):
        starts = rng.integers(0, len(x) - block + 1, size=int(np.ceil(len(x) / block)))
        sampled = np.concatenate([residuals[s:s + block] for s in starts])[:len(x)]
        slopes[i] = slope + float(centered @ sampled / (centered @ centered))
    low, high = np.quantile(slopes, [.0125, .9875])
    result.update(status="exploratory_interval", interval=[float(low), float(high)],
                  interval_level=.975, bootstrap_block_years=block,
                  bootstrap_samples=bootstrap_samples, seed=2026,
                  excludes_zero=bool(low > 0 or high < 0))
    return result
