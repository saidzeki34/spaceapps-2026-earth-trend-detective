"""Observed CAMELS-CH v0.9 flow: historical archive, never current FOEN flow."""
import io
import re
import zipfile

import httpx
import numpy as np
import pandas as pd

from mountain_water.contracts import FlowSeries, Provenance, ProviderResult, Status, utc_now
from mountain_water.data.archive import ARCHIVE_URL, fetch_member
from mountain_water.data.base import http_failure
from mountain_water.services.cache import JsonCache, cache_key

ARCHIVE_VERSION = "0.9 / Zenodo 15025258"


def parse_camels(csv_data, outlet, start, end, retrieved_at, origin="archive"):
    raw = pd.read_csv(csv_data, comment="#", encoding="latin1")
    required = {"date", "discharge_vol(m3/s)"}
    if not required.issubset(raw):
        raise ValueError("Expected CAMELS-CH observation-based date and discharge_vol(m3/s) columns.")
    days = pd.to_datetime(raw.date, format="%Y-%m-%d", errors="raise")
    if days.duplicated().any() or not days.is_monotonic_increasing:
        raise ValueError("Archive dates must be unique and ordered.")
    if (days < pd.Timestamp("1981-01-01")).any() or (days > pd.Timestamp("2020-12-31")).any():
        raise ValueError("Archive dates differ from the pinned release coverage.")
    q = pd.to_numeric(raw["discharge_vol(m3/s)"], errors="raise")
    valid = np.isfinite(q) & (q >= 0)
    begins = days.dt.tz_localize(outlet.calendar_timezone).dt.tz_convert("UTC")
    table = pd.DataFrame({"start": begins, "end": begins + pd.Timedelta(days=1),
        "discharge_m3s": q.where(valid), "raw_value": q, "valid": valid,
        "quality": "archive: no per-observation quality flags supplied", "source_date": raw.date})
    table = table[(days.dt.date >= start) & (days.dt.date <= end)]
    if table.empty:
        return ProviderResult(Status.NO_DATA, "CAMELS-CH v0.9 covers 1981-2020 only; no records in these dates.")
    provenance = Provenance("FOEN observations via CAMELS-CH / Eawag", ARCHIVE_URL,
        f"CAMELS_CH_obs_based_{outlet.station_id}", ARCHIVE_VERSION, retrieved_at,
        "CC BY 4.0 (CAMELS-CH archive); retain original-provider attribution",
        "Hoge et al. (2023), doi:10.5194/essd-15-5755-2023; FOEN/BAFU", "m3/s",
        transformations=("discharge_vol(m3/s); preserve NaN; negative/nonfinite values invalid",
            "archive daily labels represented as nominal UTC 24h intervals; subdaily timing not established",
            "no per-observation quality flags in archive; winter ice effects remain a limitation"))
    return ProviderResult(Status.READY, "Historical measured flow from CAMELS-CH v0.9 (1981-2020).",
                          FlowSeries(outlet, table, provenance, origin=origin))


class SwissProvider:
    def __init__(self, settings, member_fetcher=fetch_member):
        self.settings, self.member_fetcher = settings, member_fetcher
        self.cache = JsonCache(settings.cache_dir / "camels", 24 * 365)

    def fetch_flow(self, outlet, start, end):
        if outlet.provider != "camels_ch" or not re.fullmatch(r"2\d{3}", outlet.station_id):
            return ProviderResult(Status.UNSUPPORTED, "Select a verified Swiss CAMELS-CH gauge.")
        if start > end:
            return ProviderResult(Status.UNSUPPORTED, "Start must precede end.")
        if str(end) < "1981-01-01" or str(start) > "2020-12-31":
            return ProviderResult(Status.NO_DATA, "This archive ends on 2020-12-31; current FOEN access is not implemented.")
        member = f"camels_ch/timeseries/observation_based/CAMELS_CH_obs_based_{outlet.station_id}.csv"
        key = cache_key(provider="CAMELS-CH", version=ARCHIVE_VERSION, member=member,
                        quality="finite-nonnegative-v1", dates="1981-2020 full station member",
                        geometry=outlet.geometry, aggregation="nominal UTC daily mean")
        try:
            if self.settings.camels_ch_dir:
                # The configured root is the extracted camels_ch directory.
                path = self.settings.camels_ch_dir / "timeseries/observation_based" / f"CAMELS_CH_obs_based_{outlet.station_id}.csv"
                return parse_camels(path, outlet, start, end, utc_now(), "imported archive")
            cached = self.cache.get(key)
            if cached:
                content, retrieved, origin = cached["csv"], cached["retrieved_at"], "cached archive"
            else:
                content = self.member_fetcher(member, timeout=self.settings.timeout_seconds).decode("latin1")
                retrieved, origin = utc_now(), "fresh archive retrieval"
            result = parse_camels(io.StringIO(content), outlet, start, end, retrieved, origin)
            if result.status == Status.READY and not cached:
                self.cache.put(key, {"csv": content, "retrieved_at": retrieved})
            return result
        except httpx.HTTPStatusError as exc:
            return http_failure(exc.response) or ProviderResult(Status.ERROR, "Archive HTTP failure.")
        except (httpx.HTTPError, OSError, ValueError, KeyError, zipfile.BadZipFile):
            return ProviderResult(Status.ERROR, "CAMELS-CH archive retrieval/validation failed. Download the pinned archive and set CAMELS_CH_DIR, or import a documented flow CSV.")
