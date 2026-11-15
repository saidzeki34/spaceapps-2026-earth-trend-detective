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
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HOST = "127.0.0.1"
WEB_DIR = Path(__file__).resolve().parent / "web"
# After the window says goodbye, wait this long before stopping: a page reload says goodbye too.
CLOSE_GRACE_SECONDS = 2.5

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


@lru_cache(maxsize=1)
def _plotly_js() -> bytes:
    """Use the installed Plotly runtime, matching the backend figure version."""
    from plotly.offline import get_plotlyjs

    return get_plotlyjs().encode("utf-8")


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
            if url.path in {"/api/catalog", "/api/figure", "/api/table", "/api/courses"}:
                from mountain_water.ui import backend

                query = {key: values[0] for key, values in parse_qs(url.query).items()}
                if url.path == "/api/catalog":
                    result = backend.catalogue()
                elif url.path == "/api/figure":
                    result = backend.figure(query)
                elif url.path == "/api/table":
                    result = backend.table(query)
                else:
                    from mountain_water.ui.river_geometry import geojson_for_gauges

                    datasets = {item["id"]: item for item in backend.catalogue()["datasets"]}
                    dataset = datasets[query.get("dataset", "ch")]
                    result = geojson_for_gauges(dataset.get("gauges", []))
                self._json(result)
            elif url.path == "/vendor/plotly.min.js":
                self._send(HTTPStatus.OK, CONTENT_TYPES[".js"], _plotly_js())
            elif url.path.startswith("/api/"):
                self._json({"error": "Unknown request."}, HTTPStatus.NOT_FOUND)
            else:
                self._file(url.path)
        except KeyError:
            self._json({"error": "Unknown dataset, gauge or view."}, HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except ConnectionError:
            pass  # the window went away while we were answering
        except Exception as error:  # noqa: BLE001 - show the problem on screen instead of a dead page
            traceback.print_exc()
            self._json({"error": f"{type(error).__name__}: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/refresh":
            from mountain_water.ui import backend

            self._json(backend.refresh())
        elif path == "/api/bye":
            if self.server.auto_exit:
                self.server.closing_at = time.monotonic() + CLOSE_GRACE_SECONDS
            self._json({"ok": True})
        else:
            self._json({"error": "Unknown request."}, HTTPStatus.NOT_FOUND)

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        from plotly.utils import PlotlyJSONEncoder

        # Plotly's encoder retains typed arrays and converts NaN to JSON null.
        body = json.dumps(payload, cls=PlotlyJSONEncoder, ensure_ascii=False).encode("utf-8")
        self._send(status, CONTENT_TYPES[".json"], body)

    def _file(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else unquote(path).lstrip("/")
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
