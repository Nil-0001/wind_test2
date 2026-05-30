"""Service layer: high-level pipeline + progress streaming."""
from .pipeline import StowageResult, solve_stowage
from .progress import Event, EventKind, ProgressEmitter

__all__ = [
    "Event", "EventKind", "ProgressEmitter",
    "StowageResult", "solve_stowage",
]
