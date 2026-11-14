"""Expanding-window hindcasts: fit each model on training data only."""
from dataclasses import replace

import numpy as np
import pandas as pd

from mountain_water.analysis.flow_metrics import monthly_means
from mountain_water.models.climatology import SeasonalClimatology


def _scores(rows):
    if not rows:
        return {"n": 0, "mae_m3s": None, "rmse_m3s": None, "bias_m3s": None}
    error = np.array([r["estimate"] - r["observed"] for r in rows])
    return {"n": len(rows), "mae_m3s": float(np.abs(error).mean()),
            "rmse_m3s": float(np.sqrt(np.mean(error ** 2))), "bias_m3s": float(error.mean())}


def evaluate_hindcasts(history, model_factory=SeasonalClimatology, *, max_origins=5) -> dict:
    truth = monthly_means(history).dropna(subset=["value"])
    if truth.empty:
        return {"status": "insufficient_evidence", "n": 0, "folds": []}
    first, last = int(truth.year.min()), int(truth.year.max())
    origins = list(range(first + 5, last + 1))[-max_origins:]
    rows, baseline_rows, folds = [], [], []
    for year in origins:
        issue = pd.Timestamp(year, 1, 1, tz=history.outlet.calendar_timezone).tz_convert("UTC")
        # Pass no test rows to the model, including preprocessing and feature discovery.
        train = replace(history, table=history.table[history.table.end <= issue].copy())
        forecast = model_factory().fit_predict(train, issue.tz_convert(history.outlet.calendar_timezone).date())
        benchmark = SeasonalClimatology().fit_predict(train, issue.tz_convert(history.outlet.calendar_timezone).date())
        matches = []
        if len(forecast.table):
            if (forecast.table.start < issue).any():
                raise ValueError("Model emitted a target before its issue date.")
            pairs = forecast.table.merge(truth, on=["start", "end"], how="inner", validate="one_to_one")
            for row in pairs.itertuples():
                matches.append({"origin": year, "month": row.month,
                                "estimate": row.estimate_m3s, "observed": row.value})
            if forecast.interval_type == "prediction" and {"lower", "upper"}.issubset(pairs):
                for record, row in zip(matches, pairs.itertuples(), strict=True):
                    record["interval_covered"] = row.lower <= row.value <= row.upper
        if len(benchmark.table):
            pairs = benchmark.table.merge(truth, on=["start", "end"], how="inner", validate="one_to_one")
            baseline_rows.extend({"origin": year, "month": r.month, "estimate": r.estimate_m3s,
                                  "observed": r.value} for r in pairs.itertuples())
        rows.extend(matches)
        folds.append({"issue_date": issue.isoformat(), "training_end": str(train.table.end.max()),
                      "target_months": len(forecast.table), "scored_months": len(matches),
                      "status": forecast.status})
    result = {"status": "evaluated" if rows else "insufficient_evidence", **_scores(rows),
              "coverage": len(rows) / (12 * len(origins)) if origins else 0,
              "folds": folds, "baseline": _scores(baseline_rows),
              "seasonal": {str(m): _scores([r for r in rows if r["month"] == m]) for m in range(1, 13)},
              "policy": "Last up to five eligible January origins; expanding training, minimum five years. No model tuning on test data."}
    intervals = [r["interval_covered"] for r in rows if "interval_covered" in r]
    result["prediction_interval_coverage"] = float(np.mean(intervals)) if intervals else None
    return result
