"""NASA MODIS catchment summaries via authorized Earth Engine; no synthetic fallback."""
from datetime import timedelta

import pandas as pd

from mountain_water.contracts import DriverSeries, Provenance, ProviderResult, Status, utc_now
from mountain_water.data.quality import MODIS_QUALITY_POLICY, MODIS_REJECT_BITS
from mountain_water.services.cache import JsonCache, cache_key

PRODUCT = "MODIS/061/MOD10A1"
PRODUCT_URL = "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1"


class MODISProvider:
    def __init__(self, settings, ee_module=None):
        self.settings, self.ee = settings, ee_module
        self.cache = JsonCache(settings.cache_dir / "modis", settings.cache_ttl_hours)

    def fetch_drivers(self, outlet, start, end):
        if not self.settings.earth_engine_project:
            return ProviderResult(Status.AUTHENTICATION_REQUIRED,
                "Set EARTH_ENGINE_PROJECT and run earthengine authenticate for your authorized project, or import a documented catchment export.")
        if not outlet.geometry:
            return ProviderResult(Status.UNSUPPORTED,
                                  "A verified upstream catchment polygon is required for NASA aggregation.")
        if start > end or (end - start).days > 366 * 10:
            return ProviderResult(Status.UNSUPPORTED, "NASA requests are bounded to ten years; choose a shorter analysis period.")
        key = cache_key(provider="Earth Engine / NASA NSIDC", product=PRODUCT, version="061",
            geometry=outlet.geometry, crs="EPSG:4326", start=start, end=end,
            grid="native band projection and transform", quality=MODIS_QUALITY_POLICY,
            aggregation="area-weighted valid NDSI mean; daily composite labels; v1")
        cached = self.cache.get(key)
        if cached:
            try:
                return self._result(outlet, cached, "cached")
            except (ValueError, KeyError, TypeError):
                return ProviderResult(Status.ERROR, "Cached NASA data failed validation; refresh the affected local cache entry.")
        try:
            if self.ee is None:
                import ee
                self.ee = ee
            ee = self.ee
            ee.Initialize(project=self.settings.earth_engine_project)
            ee.data.setDeadline(60000)
        except Exception:
            return ProviderResult(Status.AUTHENTICATION_REQUIRED,
                "Earth Engine initialization failed. Verify project registration, API access and local authentication.")
        try:
            geometry = ee.Geometry(outlet.geometry)
            cursor, rows = start, []
            while cursor <= end:
                stop = min(cursor + timedelta(days=366), end + timedelta(days=1))
                collection = ee.ImageCollection(PRODUCT).filterDate(str(cursor), str(stop)).filterBounds(geometry)

                def summarize(image):
                    snow = image.select("NDSI_Snow_Cover")
                    valid = (snow.gte(0).And(snow.lte(100))
                        .And(image.select("NDSI_Snow_Cover_Basic_QA").lte(1))
                        .And(image.select("NDSI_Snow_Cover_Algorithm_Flags_QA")
                             .bitwiseAnd(MODIS_REJECT_BITS).eq(0)))
                    area = ee.Image.pixelArea()
                    bands = (snow.updateMask(valid).multiply(area).rename("weighted")
                        .addBands(area.updateMask(valid).rename("accepted"))
                        .addBands(area.rename("total")))
                    sums = bands.reduceRegion(reducer=ee.Reducer.sum(), geometry=geometry,
                        crs=snow.projection(), crsTransform=snow.projection().transform(),
                        maxPixels=10000000, tileScale=4)
                    return ee.Feature(None, sums).set("date", image.date().format("YYYY-MM-dd"))

                features = ee.FeatureCollection(collection.map(summarize)).getInfo()["features"]
                for feature in features:
                    p = feature["properties"]
                    total, accepted = p.get("total"), p.get("accepted") or 0
                    if not total or total <= 0:
                        raise ValueError("No raster area for catchment.")
                    fraction = min(1., max(0., accepted / total))
                    value = p.get("weighted") / accepted if accepted and p.get("weighted") is not None else None
                    rows.append({"date": p["date"], "value": value if fraction >= .5 else None,
                                 "valid_area_fraction": fraction})
                cursor = stop
            if not rows:
                return ProviderResult(Status.NO_DATA, "No MODIS images for the requested catchment and dates.")
            payload = {"rows": rows, "retrieved_at": utc_now(), "start": str(start), "end": str(end)}
            result = self._result(outlet, payload, "fresh")
            self.cache.put(key, payload)
            return result
        except Exception as exc:
            # Never expose provider exception text: it may contain credential or request details.
            status = Status.PENDING if any(s in str(exc).lower() for s in ("quota", "429", "timed out")) else Status.ERROR
            return ProviderResult(status, "NASA aggregation did not complete. Try a shorter date window; check project quotas and product availability.")

    def _result(self, outlet, payload, origin):
        t = pd.DataFrame(payload["rows"])
        if t.date.duplicated().any():
            raise ValueError("Duplicate MODIS product dates.")
        dates = pd.date_range(payload["start"], payload["end"], tz="UTC")
        t = t.set_index(pd.to_datetime(t.date, utc=True)).reindex(dates)
        t["start"] = dates
        t["end"] = dates + pd.Timedelta(days=1)
        t["valid_area_fraction"] = t.valid_area_fraction.fillna(0.)
        provenance = Provenance("NASA NSIDC DAAC via Google Earth Engine", PRODUCT_URL, PRODUCT,
            "061", payload["retrieved_at"], "NASA Earth science data: free use; cite product DOI",
            "Hall, D. K. and G. A. Riggs, MOD10A1 v061, NASA NSIDC DAAC; doi:10.5067/MODIS/MOD10A1.061",
            "NDSI index (0-100)", "satellite_retrieval",
            (MODIS_QUALITY_POLICY, "pixel-area weighted mean on native grid; accepted-area fraction",
             "product daily date label represented at UTC midnight, not a synchronous flow measurement"))
        return ProviderResult(Status.READY, "Mean NDSI of accepted pixels; coverage >=50%. Not snow-water volume or fractional snow area.",
            DriverSeries(outlet.id, "modis_snow", t[["start", "end", "value", "valid_area_fraction"]],
                         provenance, 500, "native-grid area-weighted mean of QA-screened NDSI", origin))
