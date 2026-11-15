"""Read-only risk adapter. Uses saved observed daily discharge only."""
from mountain_water.risk_assessment.assessment import assess


def assessment(query, backend_instance=None):
    from mountain_water.ui import backend
    adapter = backend_instance if backend_instance is not None else backend._backend()
    dataset = query.get("dataset", "ch")
    if dataset not in ("ch", "no"):
        raise ValueError("Select CAMELS-CH or NVE observations, not GLDAS or the station-network summary.")
    result, state = adapter._load(dataset)
    if result is None:
        return state
    gauge = str(query.get("gauge", ""))
    if gauge not in [str(g) for g in result.gauges]:
        raise ValueError("Choose a gauge in the saved observed dataset.")
    frame = result.daily[result.daily.gauge_id.astype(str) == gauge]
    start = int(result.meta.get("settings", {}).get("hydro_year_start_month", 10))
    def pair(name, default):
        values = [int(x) for x in query.get(name, default).split(",")]
        if len(values) != 2:
            raise ValueError(f"{name} requires two comma-separated years.")
        return tuple(values)
    requirement = query.get("requirement", "").strip()
    data = assess(frame, months=[int(x) for x in query.get("months", "8,9").split(",")],
                  start_month=start, period=pair("period", "1982,2020"), baseline=pair("baseline", "1982,2001"),
                  requirement=float(requirement) if requirement else None)
    data.update(status="ready", gauge=gauge, source=state["label"],
                provenance=result.meta.get("provenance", result.meta.get("sources", {})))
    return backend._clean(data)
