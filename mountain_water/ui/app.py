"""Start RivaScope.

From the repository root::

    python -m mountain_water.ui

This starts a small server on this computer and opens RivaScope in its own
window. Closing the window stops the server. Nothing here uses Streamlit or
any other hosted service.

Options: ``--browser`` opens a normal browser tab instead of the app window,
``--no-window`` only starts the server and prints its address, ``--port``
picks the port.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

if __package__ in (None, ""):  # started as a file: make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DEFAULT_PORT = 8765
WINDOW_SIZE = "1500,940"


def _app_window_browser() -> str | None:
    """A Chromium-based browser that can show a page as a plain window without address bar."""
    candidates: list[str] = []
    if sys.platform == "win32":
        roots = [os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for relative in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
            candidates += [os.path.join(root, relative) for root in roots if root]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        names = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")
        candidates += [path for path in map(shutil.which, names) if path]
    return next((path for path in candidates if os.path.isfile(path)), None)


def open_window(url: str, in_browser_tab: bool = False) -> None:
    browser = None if in_browser_tab else _app_window_browser()
    if browser:
        subprocess.Popen([browser, f"--app={url}", f"--window-size={WINDOW_SIZE}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url)


def _read_data_in_background() -> None:
    """Load the data while the window opens, so the loading screen is short."""
    from mountain_water.ui import data_source

    data_source.warm_up()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m mountain_water.ui", description="Start RivaScope.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to listen on (default {DEFAULT_PORT})")
    parser.add_argument("--browser", action="store_true", help="open a normal browser tab instead of the app window")
    parser.add_argument("--no-window", action="store_true", help="only start the server and print its address")
    parser.add_argument("--verbose", action="store_true", help="print every request")
    args = parser.parse_args(argv)

    from mountain_water.ui.server import HOST, make_server

    server = make_server(args.port, args.verbose)
    url = f"http://{HOST}:{server.server_port}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=_read_data_in_background, daemon=True).start()

    print(f"RivaScope is running at {url}")
    if args.no_window:
        print("Open that address in a browser. Press Ctrl+C here to stop.")
    else:
        server.auto_exit = True
        open_window(url, in_browser_tab=args.browser)
        print("Close the RivaScope window, or press Ctrl+C here, to stop.")

    try:
        while server.closing_at is None or time.monotonic() < server.closing_at:
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    server.shutdown()
    print("RivaScope stopped.")


if __name__ == "__main__":
    if "streamlit" in sys.modules:
        message = "RivaScope no longer runs through Streamlit. Start it with:  python -m mountain_water.ui"
        print(message)
        raise SystemExit(message)
    main()
