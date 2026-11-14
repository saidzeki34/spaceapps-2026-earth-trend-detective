"""Portable evidence bundle, with no credentials or unlabelled synthetic data."""
import io
import json
import zipfile
from dataclasses import asdict, is_dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, pd.DataFrame):
        return json_value(value.to_dict(orient="records"))
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def evidence_bundle(result):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
        metadata = json_value(result)
        for field in ("observations", "baseline", "periods"):
            z.writestr(f"{field}.csv", getattr(result, field).to_csv(index=False))
        if result.driver_status.data:
            z.writestr("nasa_driver.csv", result.driver_status.data.table.to_csv(index=False))
        if result.forecast is not None:
            z.writestr("outlook.csv", result.forecast.table.to_csv(index=False))
        z.writestr("evidence.json", json.dumps(metadata, indent=2, allow_nan=False))
        z.writestr("README.txt", "Mountain Water Availability evidence export\n"
                   "See evidence.json for exact source versions, quality policy, requirement, coverage, "
                   "calendar, methods, model status and limitations. Historical percentiles are not prediction intervals.\n")
    return data.getvalue()
