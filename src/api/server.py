"""FastAPI server: demo page, SSE solve endpoint and CAD download."""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..output.cad_export.service import cad_export_service
from ..service.pipeline import solve_stowage
from ..service.progress import Event

app = FastAPI(title="Wind Stowage API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)
_API_DIR = Path(__file__).parent
_STATIC_DIR = _API_DIR / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
# Built SPA (Vite -> static/app); falls back to the legacy single-file demo.
_SPA_INDEX = _STATIC_DIR / "app" / "index.html"
_DEMO_HTML = _API_DIR / "demo.html"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def demo_page():
    if _SPA_INDEX.exists():
        return FileResponse(_SPA_INDEX)
    if _DEMO_HTML.exists():
        return FileResponse(_DEMO_HTML)
    return {"hint": "POST /solve with test_data JSON to start a solve."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sample")
def sample():
    """Serve bundled test_data.json for the demo page."""
    sample_path = Path(__file__).resolve().parents[2] / "data" / "test_data.json"
    if sample_path.exists():
        return FileResponse(sample_path, media_type="application/json")
    return {"error": "no sample data"}


@app.get("/favicon.ico")
def favicon():
    ico_path = _STATIC_DIR / "favicon.ico"
    if ico_path.exists():
        return FileResponse(ico_path, media_type="image/x-icon")
    svg_path = _STATIC_DIR / "favicon.svg"
    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/download/cad/latest")
def download_latest_cad():
    latest = cad_export_service.get_latest_output()
    if latest is None or not latest.exists():
        raise HTTPException(status_code=404, detail="no CAD file available yet")
    return FileResponse(
        latest,
        media_type="application/dxf",
        filename=latest.name,
    )


def _sse_format(ev: Event) -> str:
    if isinstance(ev.data, (dict, list)):
        payload = json.dumps(ev.data, ensure_ascii=False)
    else:
        payload = json.dumps(str(ev.data), ensure_ascii=False)
    return f"event: {ev.kind}\ndata: {payload}\n\n"


@app.post("/solve")
async def solve_endpoint(req: Request):
    body = await req.json()
    test_data = body.get("test_data", body if "cargoData" in body else {})
    options = body.get("options")
    time_limit_s = int(body.get("time_limit_s", 180))
    solver_name = str(body.get("solver_name", "appsi_highs"))

    if not test_data or "cargoData" not in test_data:
        return {"error": "missing test_data with cargoData"}

    q: "queue.Queue[Event | None]" = queue.Queue(maxsize=10000)

    def cb(ev: Event) -> None:
        try:
            q.put(ev, timeout=5)
        except queue.Full:
            pass  # drop log lines if frontend lags badly

    def worker() -> None:
        try:
            solve_stowage(
                test_data,
                options=options,
                progress_cb=cb,
                time_limit_s=time_limit_s,
                solver_name=solver_name,
            )
        except Exception:
            # Already emitted via emit.error inside pipeline.
            pass
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        while True:
            try:
                ev = await asyncio.to_thread(q.get, True, 1.0)
            except queue.Empty:
                yield ":heartbeat\n\n"
                await asyncio.sleep(0)
                continue
            if ev is None:
                break
            yield _sse_format(ev)
            await asyncio.sleep(0)
            if ev.kind in ("result", "error"):
                # Drain any remaining queued events then close.
                while True:
                    try:
                        nxt = q.get_nowait()
                    except queue.Empty:
                        break
                    if nxt is None:
                        return
                    yield _sse_format(nxt)
                    await asyncio.sleep(0)
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
