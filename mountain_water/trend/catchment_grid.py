"""Map CAMELS-CH catchment outlines onto a regular lat/lon grid (e.g. the GLDAS 0.25° grid).

Each catchment gets the grid cells it overlaps and a weight per cell = overlapping area /
catchment area. Areas are computed in the shapefile's projected CRS (CH1903+/LV95 for CAMELS-CH),
so weights are true area fractions.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

CATCHMENT_SHAPEFILE = "catchment_delineations/CAMELS_CH_catchments.shp"


def _read_catchments(shp: Path, gauge_ids: list[str] | None) -> tuple[dict, str]:
    import shapefile  # pyshp
    from shapely.geometry import shape
    from shapely.validation import make_valid

    reader = shapefile.Reader(str(shp))
    fields = [f.name for f in reader.fields[1:]]
    id_field = next(f for f in fields if f.lower() == "gauge_id")
    wanted = set(gauge_ids) if gauge_ids is not None else None
    polygons = {}
    for rec, shp_obj in zip(reader.iterRecords(), reader.iterShapes()):
        raw = rec[id_field]
        gid = str(int(raw)) if isinstance(raw, float) and raw.is_integer() else str(raw)
        if wanted is None or gid in wanted:
            polygons[gid] = make_valid(shape(shp_obj.__geo_interface__))
    prj = shp.with_suffix(".prj")
    crs_wkt = prj.read_text() if prj.exists() else "EPSG:2056"
    return polygons, crs_wkt


def cell_weights(
    shp: Path,
    gauge_ids: list[str] | None = None,
    resolution: float = 0.25,
    origin: float = 0.0,
) -> pd.DataFrame:
    """Rows: gauge_id, cell_lat, cell_lon (cell centres), weight, catchment_area_km2.

    Cells are ``resolution``-degree boxes whose edges sit on multiples of ``resolution`` offset by
    ``origin`` (GLDAS 0.25°: edges at ..., 46.0, 46.25, ...; centres at 46.125, 46.375, ...).
    """
    import shapely
    from pyproj import CRS, Transformer
    from shapely.geometry import box

    polygons, crs_wkt = _read_catchments(shp, gauge_ids)
    to_wgs = Transformer.from_crs(CRS.from_user_input(crs_wkt), "EPSG:4326", always_xy=True)
    to_proj = Transformer.from_crs("EPSG:4326", CRS.from_user_input(crs_wkt), always_xy=True)

    def transform(tr: Transformer, geom):
        return shapely.transform(geom, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))

    rows = []
    for gid, poly in polygons.items():
        area = poly.area
        lon0, lat0, lon1, lat1 = transform(to_wgs, poly).bounds
        i0 = math.floor((lon0 - origin) / resolution)
        i1 = math.floor((lon1 - origin) / resolution)
        j0 = math.floor((lat0 - origin) / resolution)
        j1 = math.floor((lat1 - origin) / resolution)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                west, south = origin + i * resolution, origin + j * resolution
                cell = box(west, south, west + resolution, south + resolution).segmentize(resolution / 20)
                overlap = poly.intersection(transform(to_proj, cell)).area
                if overlap > 0:
                    rows.append(dict(
                        gauge_id=gid,
                        cell_lat=round(south + resolution / 2, 6),
                        cell_lon=round(west + resolution / 2, 6),
                        weight=overlap / area,
                        catchment_area_km2=area / 1e6,
                    ))
    out = pd.DataFrame(rows, columns=["gauge_id", "cell_lat", "cell_lon", "weight", "catchment_area_km2"])
    # Normalise so weights sum to exactly 1 per catchment despite projection/rounding effects.
    out["weight"] = out["weight"] / out.groupby("gauge_id")["weight"].transform("sum")
    return out


def weighted_mean(cell_values: pd.DataFrame, weights: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Area-weighted catchment mean from per-cell daily values.

    ``cell_values``: cell_lat, cell_lon, date, <columns>. Cells without data on a day are left
    out and the remaining weights renormalised (e.g. lake cells that are masked in GLDAS).
    """
    d = weights.merge(cell_values, on=["cell_lat", "cell_lon"], how="inner")
    out = []
    for col in columns:
        if col not in d:
            continue
        valid = d[col].notna()
        w = d["weight"].where(valid, 0.0)
        tmp = d.assign(_wx=(d[col].fillna(0.0) * w), _w=w)
        g = tmp.groupby(["gauge_id", "date"])[["_wx", "_w"]].sum()
        out.append((g["_wx"] / g["_w"].replace(0.0, np.nan)).rename(col))
    return pd.concat(out, axis=1).reset_index()
