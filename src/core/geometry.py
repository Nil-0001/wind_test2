"""Geometric utilities (polygon containment, rectangle ops, intervals)."""
from __future__ import annotations

from typing import Iterable

from .data_models import Polygon


# ---------------------------------------------------------------------------
# Point / polygon
# ---------------------------------------------------------------------------
def point_in_polygon(px: float, py: float, polygon: Polygon, tol: float = 1e-6) -> bool:
    """Ray-casting; returns True if point on edge or inside."""
    pts = polygon.points
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        # Edge case: on edge
        if _on_segment(px, py, xi, yi, xj, yj, tol):
            return True
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi + 1e-30) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _on_segment(px: float, py: float, x1: float, y1: float,
                x2: float, y2: float, tol: float) -> bool:
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > tol * max(1.0, abs(x2 - x1) + abs(y2 - y1)):
        return False
    if min(x1, x2) - tol <= px <= max(x1, x2) + tol and \
       min(y1, y2) - tol <= py <= max(y1, y2) + tol:
        return True
    return False


def rect_in_polygon(x1: float, y1: float, x2: float, y2: float,
                    polygon: Polygon, tol: float = 1e-6) -> bool:
    """All four corners of axis-aligned rectangle inside polygon."""
    corners = ((x1, y1), (x1, y2), (x2, y2), (x2, y1))
    return all(point_in_polygon(cx, cy, polygon, tol) for cx, cy in corners)


# ---------------------------------------------------------------------------
# Interval / rectangle utilities
# ---------------------------------------------------------------------------
def intervals_overlap(a1: float, a2: float, b1: float, b2: float,
                      strict: bool = False) -> bool:
    if strict:
        return a1 < b2 and b1 < a2
    return a1 <= b2 and b1 <= a2


def interval_overlap_length(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def rects_overlap(ax1: float, ay1: float, ax2: float, ay2: float,
                  bx1: float, by1: float, bx2: float, by2: float,
                  strict: bool = True) -> bool:
    if strict:
        return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2
    return ax1 <= bx2 and bx1 <= ax2 and ay1 <= by2 and by1 <= ay2


def expand_rect(x1: float, y1: float, x2: float, y2: float,
                dx: float = 0.0, dy: float = 0.0) -> tuple[float, float, float, float]:
    return (x1 - dx, y1 - dy, x2 + dx, y2 + dy)


# ---------------------------------------------------------------------------
# Layer 3 height segments
# ---------------------------------------------------------------------------
def x_range_in_segment(cx1: float, cx2: float,
                       segments: Iterable[dict]) -> dict | None:
    """Return the segment fully containing [cx1, cx2], else None."""
    for seg in segments:
        keys = sorted(k for k in seg.keys() if k.startswith("x"))
        sx1 = seg[keys[0]]
        sx2 = seg[keys[1]]
        if sx1 - 1e-6 <= cx1 and cx2 <= sx2 + 1e-6:
            return seg
    return None


def min_height_over_x_range(cx1: float, cx2: float,
                            segments: Iterable[dict]) -> float:
    """Minimum segment height across [cx1, cx2]; +inf if no overlap."""
    best = float("inf")
    found = False
    for seg in segments:
        keys = sorted(k for k in seg.keys() if k.startswith("x"))
        sx1 = seg[keys[0]]
        sx2 = seg[keys[1]]
        if intervals_overlap(cx1, cx2, sx1, sx2, strict=True):
            best = min(best, seg["height"])
            found = True
    return best if found else float("inf")
