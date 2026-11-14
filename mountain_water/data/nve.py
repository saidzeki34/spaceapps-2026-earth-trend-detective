"""NVE HydAPI v1 daily mean discharge. Requires a caller-owned API key."""
from dataclasses import replace
from datetime import timedelta

import httpx
import pandas as pd

from mountain_water.config import Settings
from mountain_water.contracts import FlowSeries, Provenance, ProviderResult, Status, utc_now
from mountain_water.data.base import http_failure
from mountain_water.data.quality import NVE_QUALITY_POLICY, nve_valid
from mountain_water.services.cache import JsonCache, cache_key

API = "https://hydapi.nve.no/api/v1/Observations"


def parse_observations(payload: dict, outlet, start, end, retrieved_at=None, origin="fresh"):
    rows, versions = [], set()
    for series in payload.get("data", []):
        if str(series.get("stationId")) != outlet.station_id or series.get("parameter") != 1001:
            raise ValueError("HydAPI response station or parameter does not match the request.")
        if series.get("unit") not in ("m3/s", "m³/s") or str(series.get("method")).lower() != "mean":
            raise ValueError("HydAPI response is not mean discharge in m3/s.")
        versions.add(str(series.get("serieVersionNo", "unknown")))
        for item in series.get("observations", []):
            timestamp = pd.Timestamp(item["time"])
            if timestamp.tzinfo is None or timestamp.tz_convert("UTC").hour != 11:
                raise ValueError("Expected NVE daily timestamps at 11:00 UTC.")
            if timestamp.minute or timestamp.second:
                raise ValueError("Unexpected NVE daily timestamp precision.")
            day = timestamp.tz_convert("UTC").date()
            if not start <= day <= end:
                continue
            begin = timestamp.tz_convert("UTC") - pd.Timedelta(hours=12)
            value, quality, correction = item.get("value"), item.get("quality"), item.get("correction")
            valid = nve_valid(value, quality, correction)
            rows.append({"start": begin, "end": begin + pd.Timedelta(days=1),
                         "discharge_m3s": value if valid else None, "raw_value": value,
                         "source_timestamp": item["time"], "quality": f"{quality}/{correction}",
                         "valid": valid})
    if not rows:
        return ProviderResult(Status.NO_DATA, "NVE returned no discharge observations in these dates.")
    table = pd.DataFrame(rows).sort_values("start")
    provenance = Provenance("NVE", API, outlet.station_id + "/1001", ",".join(sorted(versions)),
                            retrieved_at or utc_now(), "NLOD", "Norwegian Water Resources and Energy Directorate",
                            "m3/s", transformations=(NVE_QUALITY_POLICY,
                            "daily 11Z labels mapped to fixed-CET midnight intervals (timestamp -12h)",))
    return ProviderResult(Status.READY, "NVE daily mean discharge; conservative controlled-data filter.",
                          FlowSeries(outlet, table, provenance, origin=origin))


class NVEProvider:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client
        self.cache = JsonCache(settings.cache_dir / "nve", settings.cache_ttl_hours)

    def fetch_flow(self, outlet, start, end):
        if not self.settings.nve_api_key:
            return ProviderResult(Status.AUTHENTICATION_REQUIRED, "Set NVE_API_KEY in .env, or import a real flow CSV and its provenance.")
        if outlet.provider != "nve" or start > end or (end - start).days > 365 * 80:
            return ProviderResult(Status.UNSUPPORTED, "Unsupported outlet or date range for NVE.")
        parts, origins = [], []
        client = self.client or httpx.Client(timeout=self.settings.timeout_seconds)
        try:
            cursor = start
            while cursor <= end:
                stop = min(cursor + timedelta(days=364), end)
                key = cache_key(provider="nve", version="v1", station=outlet.station_id,
                                start=cursor, end=stop, parameter=1001, resolution=1440,
                                aggregation="Mean", quality=NVE_QUALITY_POLICY,
                                calendar="fixed-CET", geometry=outlet.geometry)
                cached = self.cache.get(key)
                if cached:
                    payload, retrieved = cached["response"], cached["retrieved_at"]
                    origins.append("cached")
                else:
                    response = client.get(API, params={"StationId": outlet.station_id, "Parameter": 1001,
                        "ResolutionTime": 1440, "ReferenceTime": f"{cursor}/{stop}T23:59:59Z"},
                        headers={"X-API-Key": self.settings.nve_api_key, "Accept": "application/json"})
                    failure = http_failure(response)
                    if failure:
                        return failure
                    payload, retrieved = response.json(), utc_now()
                    origins.append("fresh")
                parsed = parse_observations(payload, outlet, cursor, stop, retrieved, origins[-1])
                if parsed.status == Status.READY:
                    parts.append(parsed.data)
                    if not cached:
                        self.cache.put(key, {"response": payload, "retrieved_at": retrieved})
                cursor = stop + timedelta(days=1)
            if not parts:
                return ProviderResult(Status.NO_DATA, "No NVE daily flow in the requested range.")
            table = pd.concat([p.table for p in parts], ignore_index=True)
            retrievals = sorted({p.provenance.retrieved_at for p in parts})
            provenance = replace(parts[0].provenance,
                version=",".join(sorted({v for p in parts for v in p.provenance.version.split(",")})),
                retrieved_at=retrievals[-1],
                transformations=parts[0].provenance.transformations +
                    ("Chunk retrieval timestamps: " + ", ".join(retrievals),))
            return ProviderResult(Status.READY, "NVE daily means, quality screened.",
                FlowSeries(outlet, table, provenance,
                           origin="cached" if set(origins) == {"cached"} else "fresh / cached"))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
            return ProviderResult(Status.ERROR, "NVE retrieval or response validation failed. Check access and provider schema; no substitute data were used.")
        finally:
            if self.client is None:
                client.close()
