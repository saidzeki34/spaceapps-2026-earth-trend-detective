"""Annual 'when does water arrive' metrics. Days are counted from the start of the hydrological year.

Timing is only computed for years without remaining gaps (after short-gap filling), because
cumulative-volume dates shift when days are missing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FLOW = "discharge_vol"


def _timing_one_year(doy: np.ndarray, q: np.ndarray) -> dict[str, float]:
    nan = dict(com_doy=np.nan, half_volume_doy=np.nan, peak_doy=np.nan, onset_doy=np.nan, low_flow_doy=np.nan)
    if len(q) < 360 or np.isnan(q).any() or q.sum() <= 0:
        return nan
    cum = np.cumsum(q) / q.sum()
    departure = np.cumsum(q - q.mean())
    min7 = pd.Series(q).rolling(7, center=True, min_periods=7).mean().to_numpy()
    return dict(
        com_doy=float((doy * q).sum() / q.sum()),
        half_volume_doy=float(doy[np.searchsorted(cum, 0.5)]),
        peak_doy=float(doy[np.argmax(q)]),
        # Cumulative departure from the annual mean is lowest when flow rises above the mean for good.
        onset_doy=float(doy[np.argmin(departure)]),
        low_flow_doy=float(doy[np.nanargmin(min7)]),
    )


def annual_timing_metrics(daily: pd.DataFrame, flow: str = FLOW) -> pd.DataFrame:
    rows = []
    for (gauge_id, year), grp in daily.sort_values(["gauge_id", "date"]).groupby(["gauge_id", "hydro_year"]):
        rec = _timing_one_year(grp["hydro_doy"].to_numpy(), grp[flow].to_numpy(dtype=float))
        rows.append({"gauge_id": gauge_id, "hydro_year": year, **rec})
    return pd.DataFrame(rows)
