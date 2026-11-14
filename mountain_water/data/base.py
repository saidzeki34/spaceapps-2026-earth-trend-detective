"""Provider interfaces and bounded HTTP error handling."""
from datetime import date
from typing import Protocol

import httpx

from mountain_water.contracts import DriverSeries, FlowSeries, Outlet, ProviderResult, Status


class FlowProvider(Protocol):
    def fetch_flow(self, outlet: Outlet, start: date, end: date) -> ProviderResult[FlowSeries]: ...


class DriverProvider(Protocol):
    def fetch_drivers(self, outlet: Outlet, start: date, end: date) -> ProviderResult[DriverSeries]: ...


def http_failure(response: httpx.Response) -> ProviderResult | None:
    if response.status_code in (401, 403):
        return ProviderResult(Status.AUTHENTICATION_REQUIRED,
                              "Provider denied access. Check the documented credentials and permissions.")
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "60")
        return ProviderResult(Status.PENDING, "Provider rate limit reached. Retry later.",
                              retry_after_seconds=min(int(retry), 3600) if retry.isdigit() else 60)
    if response.status_code >= 400:
        return ProviderResult(Status.ERROR, f"Provider returned HTTP {response.status_code}.")
    return None
