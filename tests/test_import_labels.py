import io
import json
from dataclasses import asdict, replace

import pytest

from mountain_water.data.csv_import import import_driver, import_flow


def test_nonobserved_import_cannot_appear_as_measured_flow(outlet, flow_factory):
    flow = flow_factory([1])
    metadata = {"outlet_id": outlet.id, "calendar_timezone": "UTC",
        "meaning": "interval_average", "provenance": asdict(flow.provenance)}
    with pytest.raises(ValueError, match="observed provenance"):
        import_flow(io.StringIO(flow.table.to_csv(index=False)), json.dumps(metadata),
                    replace(outlet, provider="nve"))


def test_driver_import_cannot_receive_incorrect_ndsi_labels(outlet, flow_factory):
    provenance = asdict(flow_factory([1]).provenance)
    metadata = {"outlet_id": outlet.id, "variable": "temperature", "provenance": provenance,
                "spatial_resolution_m": 500, "aggregation": "synthetic import validation fixture"}
    csv = "start,end,value,valid_area_fraction\n2020-01-01T00:00:00Z,2020-01-02T00:00:00Z,50,1\n"
    with pytest.raises(ValueError, match="MODIS"):
        import_driver(io.StringIO(csv), json.dumps(metadata), outlet)
    metadata["variable"] = "modis_snow"
    provenance.update(identifier="MODIS/061/MOD10A1", version="061", units="NDSI index (0-100)",
                      kind="satellite_retrieval")
    result = import_driver(io.StringIO(csv), json.dumps(metadata), outlet)
    assert "not independently authenticated" in result.origin
    with pytest.raises(ValueError, match="coverage"):
        import_driver(io.StringIO(csv.replace(",50,1", ",50,0.4")), json.dumps(metadata), outlet)
