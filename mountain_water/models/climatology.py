"""Monthly seasonal baseline; empirical spread is not forecast uncertainty."""
from dataclasses import replace

import pandas as pd

from mountain_water.analysis.flow_metrics import monthly_means
from mountain_water.contracts import ForecastResult


class SeasonalClimatology:
    name = "seasonal_climatology"

    def fit_predict(self, history, issue_date):
        issue = pd.Timestamp(issue_date, tz=history.outlet.calendar_timezone).tz_convert("UTC")
        train = replace(history, table=history.table[history.table.end <= issue])
        monthly = monthly_means(train).dropna(subset=["value"])
        groups = monthly.groupby("month").value
        counts = groups.count()
        result = ForecastResult("unavailable", issue.isoformat(), model=self.name,
            training={"start": str(monthly.start.min()) if len(monthly) else None,
                      "end": str(monthly.end.max()) if len(monthly) else None,
                      "complete_months": len(monthly), "minimum_samples_per_month": 3},
            assumptions=["Calendar-month historical means repeat; no future weather is observed or used.",
                "At least three complete training months for every calendar month are required.",
                "Historical 10th-90th percentiles describe past variability, not calibrated prediction intervals.",
                "Future reservoir operations, abstractions, glacier changes and climate changes are not modelled."])
        if len(counts) != 12 or (counts < 3).any():
            return result
        local_issue = issue.tz_convert(history.outlet.calendar_timezone)
        first = local_issue.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if local_issue != first:
            first += pd.DateOffset(months=1)
        starts = pd.date_range(first, periods=12, freq="MS")
        rows = []
        for start in starts:
            values = groups.get_group(start.month)
            rows.append({"start": start.tz_convert("UTC"),
                "end": (start + pd.DateOffset(months=1)).tz_convert("UTC"),
                "estimate_m3s": float(values.mean()), "p10": float(values.quantile(.1)),
                "p90": float(values.quantile(.9)), "count": len(values)})
        result.table = pd.DataFrame(rows)
        result.status = "baseline_only"
        if (issue - monthly.end.max()).days > 365:
            result.assumptions.append("Training observations end more than a year before issue date; stale-history baseline only.")
        return result
