"""Constraint 6: no head-to-head cargoes on the same supporting board.

For each placement p with an end resting on board X, we forbid any other
placement from intruding into the strip from p's end to X's far edge,
taken across p's full y-extent.

Implementation: read each placement's `supporting_boards` (already
determined at candidate generation), pick its leftmost/rightmost board
by x_min, build the two forbidden zones, and convert overlap with any
other placement's bbox into a pairwise incompatibility.
"""
from __future__ import annotations

import pyomo.environ as pyo

from ..core.geometry import rects_overlap
from .base import ConstraintBase, ModelContext


class C06NoHeadToHead(ConstraintBase):
    name = "C06_no_head_to_head"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        zones_by_pid = self._compute_zones(ctx)
        pairs = self._collect_pairs(ctx, zones_by_pid)
        m.set_c6_pairs = pyo.Set(initialize=pairs, dimen=2)

        def rule(model, p1, p2):
            return ctx.y[p1] + ctx.y[p2] <= 1
        m.c6_no_head_to_head = pyo.Constraint(m.set_c6_pairs, rule=rule)

    @staticmethod
    def _build_bbox_index(ctx: ModelContext) -> dict[str, tuple]:
        idx: dict[str, tuple] = {}
        for b in ctx.bypass_boards:
            idx[b.board_id] = b.polygon.bbox
        for c in ctx.hatch_covers:
            idx[c.board_id] = c.polygon.bbox
        return idx

    def _compute_zones(self, ctx: ModelContext):
        bid2bbox = self._build_bbox_index(ctx)
        zones_by_pid: dict[int, list[tuple[float, float, float, float]]] = {}
        for p in ctx.placements:
            if p.layer < 2 or not p.supporting_boards:
                continue
            x1, x2 = p.x_extent
            y1, y2 = p.y_extent
            # Pick leftmost / rightmost supporting board by x_min.
            sorted_bids = sorted(p.supporting_boards,
                                 key=lambda bid: bid2bbox[bid][0])
            lbx_lo = bid2bbox[sorted_bids[0]][0]
            rbx_hi = bid2bbox[sorted_bids[-1]][2]
            zones: list[tuple[float, float, float, float]] = []
            if lbx_lo < x1:
                zones.append((lbx_lo, x1, y1, y2))
            if x2 < rbx_hi:
                zones.append((x2, rbx_hi, y1, y2))
            if zones:
                zones_by_pid[p.pid] = zones
        return zones_by_pid

    @staticmethod
    def _collect_pairs(ctx: ModelContext, zones_by_pid):
        pairs: set[tuple[int, int]] = set()
        by_layer: dict[int, list] = {}
        for p in ctx.placements:
            if p.layer < 2:
                continue
            by_layer.setdefault(p.layer, []).append(p)

        for layer, ps in by_layer.items():
            for i, p1 in enumerate(ps):
                z1 = zones_by_pid.get(p1.pid, [])
                if not z1:
                    continue
                for j in range(len(ps)):
                    if j == i:
                        continue
                    p2 = ps[j]
                    p2x1, p2x2 = p2.x_extent
                    p2y1, p2y2 = p2.y_extent
                    for (zx1, zx2, zy1, zy2) in z1:
                        if rects_overlap(zx1, zy1, zx2, zy2,
                                         p2x1, p2y1, p2x2, p2y2, strict=True):
                            a, b = sorted((p1.pid, p2.pid))
                            pairs.add((a, b))
                            break
        return list(pairs)
