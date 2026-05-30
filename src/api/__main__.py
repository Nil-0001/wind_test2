"""Launcher: `python -m src.api` starts the FastAPI service via uvicorn.

Avoids the RuntimeWarning that `python -m src.api.server` triggers because
the parent package's __init__ already imports server (so server ends up in
sys.modules before being run as __main__).
"""
from __future__ import annotations

import socket

import uvicorn


def main() -> None:
    host, port = "0.0.0.0", 8000
    try:
        lan_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        lan_ip = "<your-lan-ip>"
    print("=" * 64)
    print(f"  Wind Stowage API listening on {host}:{port}")
    print(f"  Open in browser:")
    print(f"    http://localhost:{port}/        (demo page)")
    print(f"    http://127.0.0.1:{port}/health  (liveness)")
    print(f"    http://{lan_ip}:{port}/         (other devices on LAN)")
    print(f"  POST /solve  →  SSE stream of progress + log + result")
    print("=" * 64)
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
