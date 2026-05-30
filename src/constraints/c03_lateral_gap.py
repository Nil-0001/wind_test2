"""Constraint 3: y-direction (lateral) gap between cargoes must be > 100 mm
when their x-extents overlap. Two placements that violate this cannot both
be selected, so we add y[p1] + y[p2] ≤ 1.
"""
from __future__ import annotations

import pyomo.environ as pyo

from ..core.geometry import interval_overlap_length, intervals_overlap
from .base import ConstraintBase, ModelContext

Y_GAP = 100  # mm


class C03LateralGap(ConstraintBase):
    name = "C03_lateral_gap_y100"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        pairs = self._collect_pairs(ctx)

        m.set_c3_pairs = pyo.Set(initialize=pairs, dimen=2)

        def rule(model, p1, p2):
            return ctx.y[p1] + ctx.y[p2] <= 1
        m.c3_lateral_gap = pyo.Constraint(m.set_c3_pairs, rule=rule)

    @staticmethod
    def _collect_pairs(ctx: ModelContext) -> list[tuple[int, int]]:
        pairs: list[tuple[int, int]] = []
        # Group by (layer, hatch_id). L1/L2/L3 cargoes never cross hatches
        # (constraint 9), so cross-hatch pairs cannot conflict. L4 has no
        # hatch concept → group by layer only.
        groups: dict[tuple, list] = {}
        for p in ctx.placements:
            key = (p.layer, p.hatch_id) if p.layer != 4 else (4, None)
            groups.setdefault(key, []).append(p)
        for ps in groups.values():
            ps.sort(key=lambda p: p.x_extent[0])
            n = len(ps)
            for i in range(n):
                p1 = ps[i]
                p1x1, p1x2 = p1.x_extent
                p1y1, p1y2 = p1.y_extent
                for j in range(i + 1, n):
                    p2 = ps[j]
                    p2x1, p2x2 = p2.x_extent
                    # Sorted by x1 ascending: once p2.x1 >= p1.x2, every
                    # subsequent p2'.x1 also >= p1.x2 → no x-overlap. Break.
                    if p2x1 >= p1x2:
                        break
                    if not intervals_overlap(p1x1, p1x2, p2x1, p2x2, strict=True):
                        continue
                    p2y1, p2y2 = p2.y_extent
                    if intervals_overlap(p1y1, p1y2, p2y1, p2y2, strict=True):
                        gap = 0
                    else:
                        gap = max(p1y1, p2y1) - min(p1y2, p2y2)
                    if gap < Y_GAP:
                        pairs.append((p1.pid, p2.pid))
        return pairs
