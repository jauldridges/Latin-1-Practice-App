#!/usr/bin/env python3
"""Launcher. Runs the local web app for the review tool and the vocabulary drill.

    python run.py

Then open http://localhost:5000 on this laptop, or http://<laptop-ip>:5000 on a
phone on the same network. No accounts, no hosting.
"""

import os
import socket

from server import app


def _free_port(preferred):
    """Return the first port that actually accepts a bind.

    macOS runs AirPlay Receiver on 5000 by default, so the obvious port is
    usually taken on a Mac. Rather than making the teacher diagnose
    "Address already in use", walk a short list and use the first one free.
    An explicit PORT=... is honoured strictly: if the user names a port and it
    is busy, that is worth an error, not a silent move.
    """
    candidates = [preferred, 5050, 5001, 8000, 8080, 8800, 0]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
            except OSError:
                continue
            return s.getsockname()[1]
    return preferred


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


if __name__ == "__main__":
    requested = os.environ.get("PORT")
    if requested:
        port = int(requested)          # explicit choice: use it or fail loudly
    else:
        port = _free_port(5000)
        if port != 5000:
            print("(port 5000 was busy — macOS AirPlay Receiver often holds it)")
    print("Latin I — review tool + vocabulary drill")
    print(f"  this laptop : http://localhost:{port}")
    print(f"  on a phone  : http://{_lan_ip()}:{port}   (same wifi)")
    print("  (ctrl-C to stop)")
    # Open a browser on the laptop unless asked not to (NO_BROWSER=1).
    if os.environ.get("NO_BROWSER") != "1" and not os.environ.get("WERKZEUG_RUN_MAIN"):
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False)
