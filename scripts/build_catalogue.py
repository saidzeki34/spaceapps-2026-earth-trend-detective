"""Opt-in catalogue refresh from primary providers. Requires .[catalogue].

Downloads remain in ignored data/raw. Only selected station metadata and matched
catchment geometries are written to config/. Review the diff before committing.
"""
import csv
import json
from pathlib import Path

import httpx
import shapefile
from pyproj import CRS, Transformer

from mountain_water.data.archive import fetch_member

ROOT = Path(__file__).resolve().parents[1]
NVE = "https://kart.nve.no/enterprise/rest/services/HydrologiskeData3/MapServer"
CAMELS = "https://zenodo.org/records/15025258"


def archive_file(name):
    path = ROOT / "data/raw" / name
    if not path.exists():
        content = fetch_member(name, max_bytes=110_000_000, timeout=120)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return path


def main():
    output = ROOT / "config/catchments"
    output.mkdir(parents=True, exist_ok=True)
    params = {"where": "stasjonnr='2.32.0'", "outFields": "*", "returnGeometry": "true",
              "outSR": "4326", "f": "geojson"}
    with httpx.Client(timeout=30) as client:
        s = client.get(NVE + "/0/query", params=params)
        c = client.get(NVE + "/38/query", params=params)
        s.raise_for_status()
        c.raise_for_status()
        station, catchment = s.json()["features"][0], c.json()["features"][0]
    assert station["properties"]["compoundkey12"] == catchment["properties"]["compoundkey12"]
    (output / "nve-2.32.0.geojson").write_text(json.dumps(catchment["geometry"]), encoding="utf-8")
    p = station["properties"]
    longitude, latitude = station["geometry"]["coordinates"]
    norway = dict(id="nve-2.32.0", name="Atnasjø · Atna", country="Norway", provider="nve",
        station_id="2.32.0", latitude=latitude, longitude=longitude,
        catchment_id=str(p["feltnr"]), catchment_area_km2=catchment["properties"]["nedborfeltaareal_km2"],
        catchment_source=NVE + "/38", source_url="https://sildre.nve.no/station/2.32.0",
        supported_start="1916 (published station history; HydAPI daily coverage checked per query)",
        supported_end="provider-dependent", regulation_status=f"NVE regulation code {p['reguleringstype']}; current meaning not independently resolved",
        geometry_path="config/catchments/nve-2.32.0.geojson", calendar_timezone="Etc/GMT-1",
        notes="NVE station and total upstream catchment matched by compoundkey12. 463.3 km² mountain basin; historical report describes unregulated flow, current metadata must be reviewed. Dates/quality depend on HydAPI response.")
    shape_base = "camels_ch/catchment_delineations/CAMELS_CH_catchments"
    files = {ext: archive_file(shape_base + "." + ext) for ext in ("shp", "shx", "dbf", "prj")}
    crs = CRS.from_wkt(files["prj"].read_text())
    print("Swiss catchment source CRS:", crs.to_string())
    reader = shapefile.Reader(str(files["shp"]), encoding="latin1")
    fields = [f[0] for f in reader.fields[1:]]
    print("Catchment identity fields:", fields[:12])
    index = next(i for i, r in enumerate(reader.iterRecords()) if r.as_dict()["gauge_id"] == 2263)
    geometry = reader.shape(index).__geo_interface__
    transform = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def coordinates(value):
        if isinstance(value[0], (int, float)):
            return [round(n, 6) for n in transform.transform(*value[:2])]
        return [coordinates(child) for child in value]

    geo = {"type": geometry["type"], "coordinates": coordinates(geometry["coordinates"])}
    (output / "camels-2263.geojson").write_text(json.dumps(geo), encoding="utf-8")
    attributes = {}
    for kind in ("topographic", "humaninfluence"):
        path = archive_file(f"camels_ch/static_attributes/CAMELS_CH_{kind}_attributes.csv")
        rows = csv.DictReader(line for line in path.read_text(encoding="latin1").splitlines() if not line.startswith("#"))
        attributes[kind] = next(r for r in rows if r["gauge_id"] == "2263")
    p, h = attributes["topographic"], attributes["humaninfluence"]
    gauge_transform = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    longitude, latitude = gauge_transform.transform(float(p["gauge_easting"]), float(p["gauge_northing"]))
    swiss = dict(id="camels-2263", name="Chamuerabach · La Punt-Chamues-ch", country="Switzerland",
        provider="camels_ch", station_id="2263", latitude=latitude, longitude=longitude,
        catchment_id="2263", catchment_area_km2=float(p["area"]), catchment_source=CAMELS,
        source_url="https://www.hydrodaten.admin.ch/en/seen-und-fluesse/stations/2263",
        supported_start="1981-01-01", supported_end="2020-12-31",
        regulation_status=f"CAMELS-CH: {h['hp_count']} hydropower installations, {h['num_reservoir']} reservoirs recorded; future operations unknown",
        geometry_path="config/catchments/camels-2263.geojson", calendar_timezone="UTC",
        notes="CAMELS-CH v0.9 gauge_id joins observations, attributes and full upstream polygon. Mean catchment elevation 2544.42 m. FOEN warns of winter ice effects. Archive dates are nominal 24h days; precise subdaily timing is not established.")
    (ROOT / "config/stations.json").write_text(json.dumps([swiss, norway], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote two matched station/catchment catalogue entries; review provenance and diff.")


if __name__ == "__main__":
    main()
