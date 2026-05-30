"""Progress events emitted by the solver pipeline.

Two consumers:
- HTTP API → forwards each Event to an SSE stream.
- Library callers → can register a callback for testing / CLI logging.

Event kinds:
- progress: structured phase/pct/msg, used for progress bar
- log:      one line of solver/HiGHS stdout, for terminal stream
- result:   final payload (only emitted on success)
- error:    error message (only emitted on failure)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

EventKind = Literal["progress", "log", "result", "error"]


@dataclass(frozen=True)
class Event:
    kind: EventKind
    data: Any   # dict for progress/result, str for log/error


class ProgressEmitter:
    """Light wrapper around a user callback. Callback may be None (no-op)."""

    def __init__(self, cb: Optional[Callable[[Event], None]] = None):
        self._cb = cb

    def _emit(self, ev: Event) -> None:
        if self._cb is not None:
            self._cb(ev)

    # ---------- structured progress ----------
    def progress(self, phase: str, pct: int, msg: str = "") -> None:
        """Phase: load / candidates / build / solve / output / done."""
        self._emit(Event("progress", {"phase": phase, "pct": int(pct), "msg": msg}))

    # ---------- log line ----------
    def log(self, line: str) -> None:
        if line:
            self._emit(Event("log", line))

    # ---------- final ----------
    def result(self, payload: dict) -> None:
        self._emit(Event("result", payload))

    def error(self, message: str) -> None:
        self._emit(Event("error", message))


import io as _io


class _LineSplittingStream(_io.TextIOBase):
    """TextIOBase; collects text and emits one log Event per newline.

    Used to redirect HiGHS / pyomo stdout into the SSE log stream.
    Subclassing TextIOBase makes pyomo / highspy's writability checks happy.
    """

    def __init__(self, emitter: ProgressEmitter):
        super().__init__()
        self.emitter = emitter
        self._buf = ""

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.rstrip("\r")
                if line.strip():
                    self.emitter.log(line)
        except Exception:
            return len(s)  # never propagate; lost log lines are acceptable
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        if self._buf.strip():
            try:
                self.emitter.log(self._buf)
            except Exception:
                pass
            self._buf = ""

    def isatty(self) -> bool:
        return False
