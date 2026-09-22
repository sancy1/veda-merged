# filename: scripts/run_dashboard.py
# title: One-Command Dashboard Launcher
# layer: Verification tooling
# status: Phase 7 tooling
# description:
#     Starts the FastAPI server and opens the dashboard in the
#     default browser. One command. No separate terminals. No
#     manual URL typing.
#
# usage:
#     python scripts/run_dashboard.py
#
# source:
#     AUTHORED - Phase 7 convenience tooling.

from __future__ import annotations

import os
import threading
import time
import webbrowser

import uvicorn

from veda.interfaces.api import app


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"


def _open_browser_later() -> None:
    """Wait briefly for the server to bind, then open the browser."""
    time.sleep(2.0)
    print(f"Opening {URL}")
    webbrowser.open(URL)


def main() -> int:
    # Do NOT set a default user agent. If the caller has not
    # supplied one, the pipeline will refuse SEC requests with a
    # clear message. This avoids silently sending a placeholder
    # value to SEC.
    if not os.environ.get("SEC_API_USER_AGENT", "").strip():
        print(
            "Note: SEC_API_USER_AGENT is not set. "
            "Fixture mode will work; live mode will be refused with a clear error."
        )
        print(
            '  To enable live mode, set: '
            '$env:SEC_API_USER_AGENT = "Your Name your_email@example.com"'
        )
        print()

    print(f"Starting VEDA dashboard on {URL}")
    print("Press Ctrl+C to stop.")
    print()

    threading.Thread(target=_open_browser_later, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
