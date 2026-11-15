"""The small local web server behind the RivaScope window.

It hands out the pages in ``web/`` and answers their questions as JSON. It
uses only Python's standard library and listens on this computer only.

The data modules (pandas and the trend section) are imported on the first
request that needs them, not when this file is loaded. That lets the window
open at once and show the loading screen while the data is being read.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mountain_water.ui import controls, wording
from mountain_water.ui.state import Selection

HOST = "127.0.0.1"
WEB_DIR = Path(__file__).resolve().parent / "web"
# After the window says goodbye, wait this long before stopping: a page reload says goodbye too.
CLOSE_GRACE_SECONDS = 2.5
COMPLETE_YEAR_DAYS = 360

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def _latest_complete_year(data) -> int:
    flow_days = data.daily.dropna(subset=["discharge_vol"])["date"].dt.year.value_counts()
    complete = [year for year in data.years if flow_days.get(year, 0) >= COMPLETE_YEAR_DAYS]
    return complete[-1] if complete else data.years[-1]


def view(selection: Selection) -> dict:
    """Everything the right-hand box shows for one selection."""
    from mountain_water.ui import data_source, overview, prediction_view, risk_view, trend_view

    data = data_source.river_data(selection.river)
    year = selection.year
    if year not in data.years and year != data.prediction_year:
        year = _latest_complete_year(data)
    predicted = year == data.prediction_year
    method = controls.METHOD_MONTHLY if predicted else selection.method  # a prediction is always per month
    variables = list(selection.variables)

    if predicted:
        chart = prediction_view.chart(data, variables, year, selection.usual)
    else:
        chart = trend_view.chart(data, variables, year, method, selection.usual)
    result = {
        "river": overview.river_summary(data),
        "year": year,
        "predicted": predicted,
        "method": method,
        "chart": chart,
    }
    if "risk" in selection.sections:
        occupation = controls.OCCUPATIONS_BY_ID[selection.occupation]
        flow = prediction_view.predicted_flow(data, year) if predicted else None
        result["risk"] = risk_view.assess(data, occupation, year, flow)
    if "statistics" in selection.sections:
        result["statistics"] = trend_view.statistics(data, variables, year, predicted)
    if "physical" in selection.sections:
        result["physical"] = prediction_view.physical_model(data, year, predicted)
    return result


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, "reuse address" would let two copies listen on the same port at once.
    allow_reuse_address = os.name != "nt"
    verbose = False
    auto_exit = False  # stop when the window closes
    closing_at: float | None = None  # moment to stop, set when the window says goodbye


class Handler(BaseHTTPRequestHandler):
    server_version = "RivaScope"
    sys_version = ""

    def log_message(self, format, *args):
        if self.server.verbose:
            super().log_message(format, *args)

    def do_GET(self):
        url = urlsplit(self.path)
        self.server.closing_at = None  # someone is (still) there
        try:
            if url.path == "/api/bootstrap":
                self._json(controls.catalogue())  # the menus: ready at once
            elif url.path == "/api/rivers":
                from mountain_water.ui import overview

                self._json(overview.rivers())  # waits until the data has been read
            elif url.path == "/api/outlines":
                from mountain_water.ui import data_source

                self._json(data_source.catchment_outlines())
            elif url.path == "/api/view":
                self._json(view(Selection.from_query(parse_qs(url.query))))
            elif url.path.startswith("/api/"):
                self._json({"error": "Unknown request."}, HTTPStatus.NOT_FOUND)
            else:
                self._file(url.path)
        except KeyError:
            self._json({"error": "That river is not in the list."}, HTTPStatus.NOT_FOUND)
        except ConnectionError:
            pass  # the window went away while we were answering
        except Exception as error:  # noqa: BLE001 - show the problem on screen instead of a dead page
            traceback.print_exc()
            self._json({"error": f"{type(error).__name__}: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if urlsplit(self.path).path == "/api/bye" and self.server.auto_exit:
            self.server.closing_at = time.monotonic() + CLOSE_GRACE_SECONDS
        self._json({"ok": True})

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(wording.clean(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, CONTENT_TYPES[".json"], body)

    def _file(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_DIR / relative).resolve()
        if not target.is_relative_to(WEB_DIR) or not target.is_file():
            self._send(HTTPStatus.NOT_FOUND, CONTENT_TYPES[".txt"], b"Not found")
            return
        content_type = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(HTTPStatus.OK, content_type, target.read_bytes())


def make_server(port: int, verbose: bool = False) -> AppServer:
    """Listen on the wanted port, or on a nearby free one if it is taken."""
    for candidate in [*range(port, port + 20), 0]:
        try:
            server = AppServer((HOST, candidate), Handler)
        except OSError:
            continue
        server.verbose = verbose
        return server
    raise OSError("No free port found for RivaScope.")
