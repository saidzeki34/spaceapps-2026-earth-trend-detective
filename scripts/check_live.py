"""Opt-in network check; records honest access states and real evidence locally."""
import json
from datetime import date
from pathlib import Path

import pandas as pd

from mountain_water.config import Settings, load_outlets
from mountain_water.contracts import AssessmentRequest, RequirementSeries, Status, utc_now
from mountain_water.data.nasa import MODISProvider
from mountain_water.data.nve import NVEProvider
from mountain_water.data.swiss import SwissProvider
from mountain_water.services.assessment import run_assessment
from mountain_water.services.export import evidence_bundle, json_value


def main():
    settings = Settings.from_env()
    reports = []
    destination = Path("data/exports")
    destination.mkdir(parents=True, exist_ok=True)
    for outlet in load_outlets():
        provider = NVEProvider(settings) if outlet.provider == "nve" else SwissProvider(settings)
        request = AssessmentRequest(outlet, date(2011, 1, 1), date(2020, 12, 31),
            (2001, 2010), issue_date=date(2021, 1, 1))
        requirement = RequirementSeries(pd.DataFrame({
            "start": ["2010-01-01T00:00:00Z"], "end": ["2023-01-01T00:00:00Z"],
            "requirement_m3s": [1.]}), "Validation scenario: 1 m3/s", "Developer validation",
            "Hypothetical test scenario; not observed demand")
        result = run_assessment(request, provider, MODISProvider(settings), requirement)
        report = {"checked_at": utc_now(), "outlet": outlet.id,
            "analysis": [str(request.start), str(request.end)],
            "reference_years": request.baseline_years,
            "flow_status": result.flow_status.status, "flow_message": result.flow_status.message,
            "nasa_status": result.driver_status.status, "nasa_message": result.driver_status.message,
            "rows": len(result.observations), "metrics": result.metrics,
            "complete_seasons": int(result.periods.season_volume_m3.notna().sum()) if len(result.periods) else 0,
            "forecast_status": result.forecast.status if result.forecast else "unavailable",
            "hindcasts": result.forecast.hindcasts if result.forecast else {},
            "limitations": result.limitations}
        if result.flow_status.status == Status.READY:
            assert result.flow_status.data.provenance.kind == "observed"
            report["flow_provenance"] = result.flow_status.data.provenance
            report["origin"] = result.flow_status.data.origin
        destination.joinpath(f"live-{outlet.id}.zip").write_bytes(evidence_bundle(result))
        reports.append(json_value(report))
        print(json.dumps(reports[-1], ensure_ascii=True), flush=True)
    destination.joinpath("live-check.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
