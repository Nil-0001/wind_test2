"""Constraint 4: x-direction (longitudinal) gap between cargoes must be > 500 mm
whenever their y-extents overlap. We enforce this with pairwise y[p1]+y[p2]≤1.
"""
from __future__ import annotations

import pyomo.environ as pyo

from ..core.geometry import intervals_overlap
from .base import ConstraintBase, ModelContext

X_GAP = 500  # mm


class C04LongitudinalGap(ConstraintBase):
    name = "C04_longitudinal_gap_x500"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        pairs = self._collect_pairs(ctx)

        m.set_c4_pairs = pyo.Set(initialize=pairs, dimen=2)

        def rule(model, p1, p2):
            return ctx.y[p1] + ctx.y[p2] <= 1
        m.c4_longitudinal_gap = pyo.Constraint(m.set_c4_pairs, rule=rule)

    @staticmethod
    def _collect_pairs(ctx: ModelContext) -> list[tuple[int, int]]:
        pairs: list[tuple[int, int]] = []
        # Group by (layer, hatch_id). L1/L2/L3 don't cross hatches; L4 by layer.
        groups: dict[tuple, list] = {}
        for p in ctx.placements:
            key = (p.layer, p.hatch_id) if p.layer != 4 else (4, None)
            groups.setdefault(key, []).append(p)
        for ps in groups.values():
            ps.sort(key=lambda p: p.y_extent[0])
            n = len(ps)
            for i in range(n):
                p1 = ps[i]
                p1y1, p1y2 = p1.y_extent
                p1x1, p1x2 = p1.x_extent
                for j in range(i + 1, n):
                    p2 = ps[j]
                    p2y1, p2y2 = p2.y_extent
                    # Sorted by y1: once p2.y1 >= p1.y2, no further y-overlap.
                    if p2y1 >= p1y2:
                        break
                    if not intervals_overlap(p1y1, p1y2, p2y1, p2y2, strict=True):
                        continue
                    p2x1, p2x2 = p2.x_extent
                    if intervals_overlap(p1x1, p1x2, p2x1, p2x2, strict=True):
                        gap = 0
                    else:
                        gap = max(p1x1, p2x1) - min(p1x2, p2x2)
                    if gap < X_GAP:
                        pairs.append((p1.pid, p2.pid))
        return pairs
