"""Explicit user imports require a matching outlet and sidecar provenance."""
import json

import pandas as pd

from mountain_water.contracts import DriverSeries, FlowSeries, Provenance, RequirementSeries


def _metadata(source):
    return json.load(source) if hasattr(source, "read") else json.loads(source)


def import_flow(csv_source, metadata_source, outlet) -> FlowSeries:
    metadata = _metadata(metadata_source)
    if metadata.get("outlet_id") != outlet.id:
        raise ValueError("Import outlet_id does not match the selected outlet.")
    if metadata.get("calendar_timezone") != outlet.calendar_timezone:
        raise ValueError("Import calendar timezone must match the outlet.")
    table = pd.read_csv(csv_source, keep_default_na=True)
    if "valid" not in table or "quality" not in table:
        raise ValueError("CSV needs quality and valid columns. Document your validity policy in provenance.")
    mapped = table.valid.astype(str).str.lower().map({"true": True, "false": False})
    if mapped.isna().any():
        raise ValueError("CSV valid must contain true or false.")
    table["valid"] = mapped
    provenance = Provenance(**metadata["provenance"])
    if provenance.kind != "observed" and outlet.provider != "synthetic":
        raise ValueError("Measured-outlet imports require observed provenance; use the labelled developer demo for synthetic flow.")
    return FlowSeries(outlet, table, provenance, metadata.get("meaning", ""), "imported")


def import_driver(csv_source, metadata_source, outlet) -> DriverSeries:
    metadata = _metadata(metadata_source)
    if metadata.get("outlet_id") != outlet.id:
        raise ValueError("Driver import does not match the selected outlet.")
    provenance = Provenance(**metadata["provenance"])
    if (metadata.get("variable") != "modis_snow" or provenance.identifier != "MODIS/061/MOD10A1"
            or provenance.version != "061" or provenance.units != "NDSI index (0-100)"
            or provenance.kind != "satellite_retrieval"):
        raise ValueError("This driver import supports MODIS/061/MOD10A1 v061 NDSI index (0-100) satellite retrievals only.")
    series = DriverSeries(outlet.id, metadata["variable"], pd.read_csv(csv_source),
                          provenance, metadata["spatial_resolution_m"], metadata["aggregation"],
                          "imported; source claims supplied by user, not independently authenticated")
    values = series.table.value.dropna()
    if not values.between(0, 100).all():
        raise ValueError("MODIS NDSI values must be between 0 and 100; flagged codes are not values.")
    if (series.table.value.notna() & (series.table.valid_area_fraction < .5)).any():
        raise ValueError("Imported NDSI values below 50% valid-area coverage must be missing.")
    return series


def import_requirement(csv_source, metadata_source) -> RequirementSeries:
    metadata = _metadata(metadata_source)
    return RequirementSeries(pd.read_csv(csv_source), **metadata)
