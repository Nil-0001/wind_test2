"""Constraint 5: Layer 2/3/4 cargo's four corners must lie on a hatch cover or
bypass board.

Already enforced at candidate-generation time (we never emit a candidate whose
corners do not rest on a board). This module adds an integrity check.
"""
from __future__ import annotations

from ..core.geometry import point_in_polygon
from .base import ConstraintBase, ModelContext


class C05CornersOnBoard(ConstraintBase):
    name = "C05_corners_on_board"

    def apply(self, ctx: ModelContext) -> None:
        bypass = ctx.bypass_boards
        hatches = ctx.hatch_covers
        for p in ctx.placements:
            if p.layer == 1:
                continue
            corners = list(p.corners.values())
            for cx, cy in corners:
                if not _corner_on_any_board(cx, cy, p.layer, bypass, hatches):
                    raise AssertionError(
                        f"C5 violation: placement {p.pid} (layer {p.layer}) corner "
                        f"({cx},{cy}) does not rest on any supporting board."
                    )


def _corner_on_any_board(cx, cy, layer, bypass_boards, hatch_covers) -> bool:
    if layer in (2, 3):
        for b in bypass_boards:
            if b.layer != layer:
                continue
            if point_in_polygon(cx, cy, b.polygon):
                return True
        return False
    if layer == 4:
        for c in hatch_covers:
            if point_in_polygon(cx, cy, c.polygon):
                return True
        for b in bypass_boards:
            if point_in_polygon(cx, cy, b.polygon):
                return True
        return False
    return True
