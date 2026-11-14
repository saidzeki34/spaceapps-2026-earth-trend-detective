"""Native-interval threshold exposure, not a universal user-risk score."""
import numpy as np
import pandas as pd

from mountain_water.analysis.flow_metrics import durations
from mountain_water.contracts import RequirementSeries


def align_requirement(table: pd.DataFrame, requirement: RequirementSeries) -> pd.Series:
    """Only use a requirement covering a whole flow interval; never split a coarse mean."""
    r = requirement.table
    if r.empty:
        return pd.Series(np.nan, index=table.index)
    starts = r.start.astype("int64").to_numpy()
    positions = np.searchsorted(starts, table.start.astype("int64"), side="right") - 1
    values = []
    for row, pos in zip(table.itertuples(), positions, strict=True):
        if pos < 0 or r.iloc[pos].end < row.end:
            values.append(np.nan)
        else:
            values.append(r.iloc[pos].requirement_m3s)
    return pd.Series(values, index=table.index, dtype=float)


def assess_threshold_exposure(table: pd.DataFrame, requirement: RequirementSeries,
                              expected_seconds: float, *, allow_events=True) -> dict:
    t = table.copy().reset_index(drop=True)
    t["requirement_m3s"] = align_requirement(t, requirement)
    valid = t.valid & t.discharge_m3s.notna() & t.requirement_m3s.notna()
    delta = t.requirement_m3s - t.discharge_m3s
    seconds = durations(t)
    below = valid & (delta > 0)
    assessed = float(seconds[valid].sum())
    events = []
    active = None
    for i, row in enumerate(t.itertuples()):
        contiguous = i > 0 and t.iloc[i - 1].end == row.start
        if active is not None and (not below.iloc[i] or not contiguous):
            active["end_censored"] = not (contiguous and valid.iloc[i])
            events.append(active)
            active = None
        if below.iloc[i]:
            if active is None:
                active = {"start": row.start.isoformat(), "end": row.end.isoformat(),
                          "duration_seconds": 0., "deficit_volume_m3": 0.,
                          "start_censored": not (contiguous and valid.iloc[i - 1]),
                          "end_censored": True}
            active["end"] = row.end.isoformat()
            active["duration_seconds"] += float(seconds.iloc[i])
            active["deficit_volume_m3"] += float(delta.iloc[i] * seconds.iloc[i])
    if active is not None:
        events.append(active)
    return {"name": "river-flow threshold exposure", "requirement": requirement.name,
            "scenario_status": requirement.status, "resilience": requirement.resilience,
            "assessed_seconds": assessed, "expected_seconds": expected_seconds,
            "coverage": assessed / expected_seconds if expected_seconds else 0,
            "below_fraction": float(seconds[below].sum() / assessed) if assessed else None,
            "adequacy_fraction": float(1 - seconds[below].sum() / assessed) if assessed else None,
            "deficit_volume_m3": float((delta.clip(lower=0) * seconds)[valid].sum()) if assessed else None,
            "margin_volume_m3": float(((-delta).clip(lower=0) * seconds)[valid].sum()) if assessed else None,
            "peak_deficit_m3s": float(delta[valid].clip(lower=0).max()) if assessed else None,
            "event_count": len(events) if allow_events and assessed else None,
            "longest_event_seconds": max((e["duration_seconds"] for e in events), default=0)
            if allow_events and assessed else None,
            "events": events if allow_events else [],
            "unresolved_requirement_intervals": int(t.requirement_m3s.isna().sum()),
            "event_interpretation": "Runs of interval-average deficits; missing data censor boundaries."
            if allow_events else "Daily events withheld: monthly outlook cannot resolve daily shortages.",
            "aligned": t}
