#!/usr/bin/env python3
"""Launcher. Runs the local web app for the review tool and the vocabulary drill.

    python run.py

Then open http://localhost:5000 on this laptop, or http://<laptop-ip>:5000 on a
phone on the same network. No accounts, no hosting.
"""

import os
import socket

from server import app


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
    port = int(os.environ.get("PORT", "5000"))
    print("Latin I — review tool + vocabulary drill")
    print(f"  this laptop : http://localhost:{port}")
    print(f"  on a phone  : http://{_lan_ip()}:{port}   (same wifi)")
    app.run(host="0.0.0.0", port=port, debug=False)
