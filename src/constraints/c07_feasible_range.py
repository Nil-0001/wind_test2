"""Constraint 7: stowage feasible range + inter-layer height coupling.

Plane (footprint inside FeasibleRange polygon) and Layer-3 own height limit
are enforced at candidate-generation time. This module adds:

(a) Bypass-board disablement: if a low-layer placement's stack height
    exceeds the cumulative height up to layer L, every layer-L bypass
    board overlapping the placement is forced off.
(b) Body-collision pairs: if a low-layer placement physically reaches
    into an upper layer's z-band AND its footprint overlaps an upper
    placement's footprint, the two cannot both be selected.
"""
from __future__ import annotations

import pyomo.environ as pyo

from ..core.geometry import rects_overlap
from .base import ConstraintBase, ModelContext


class C07FeasibleRange(ConstraintBase):
    name = "C07_feasible_range_height_coupling"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        l1 = self._layer_limits(ctx, 1)
        l2 = self._layer_limits(ctx, 2)
        l3 = self._layer_limits(ctx, 3)

        coupled, body_pairs = self._compute_couples_and_pairs(ctx, l1, l2, l3)

        m.set_c7_couples = pyo.Set(initialize=coupled, dimen=2)
        m.c7_height_coupling = pyo.Constraint(
            m.set_c7_couples,
            rule=lambda mdl, pid, bid: ctx.y[pid] + ctx.z[bid] <= 1)

        m.set_c7_body = pyo.Set(initialize=body_pairs, dimen=2)
        m.c7_body_collision = pyo.Constraint(
            m.set_c7_body,
            rule=lambda mdl, p1, p2: ctx.y[p1] + ctx.y[p2] <= 1)

    @staticmethod
    def _layer_limits(ctx, layer):
        out: dict[str, float] = {}
        for fr in ctx.feasible_ranges:
            if fr.layer != layer or fr.height_limit is None:
                continue
            out[fr.hatch_id] = float(fr.height_limit)
        return out

    @staticmethod
    def _affected_upper_layers(low_layer, stack_h, hatch, l1, l2, l3):
        """Return list of upper layers whose z-band the over-tall cargo
        physically intrudes into. L3 cannot break its own ceiling
        (filtered at candidate gen) so low_layer never == 3.
        """
        h1 = l1.get(hatch, float("inf")) if hatch else float("inf")
        h2 = l2.get(hatch, float("inf")) if hatch else float("inf")
        h3 = l3.get(hatch, float("inf")) if hatch else float("inf")
        layers = []
        if low_layer == 1:
            if stack_h > h1:                       layers.append(2)
            if stack_h > h1 + h2:                  layers.append(3)
            if stack_h > h1 + h2 + h3:             layers.append(4)
        elif low_layer == 2:
            if stack_h > h2:                       layers.append(3)
            if stack_h > h2 + h3:                  layers.append(4)
        return layers

    def _compute_couples_and_pairs(self, ctx, l1, l2, l3):
        coupled: list[tuple[int, str]] = []
        body_pairs: list[tuple[int, int]] = []

        upper_by_layer: dict[int, list] = {2: [], 3: [], 4: []}
        for p in ctx.placements:
            if p.layer in upper_by_layer:
                upper_by_layer[p.layer].append(p)

        bypass_by_layer: dict[int, list] = {2: [], 3: []}
        for b in ctx.bypass_boards:
            if b.layer in bypass_by_layer:
                bypass_by_layer[b.layer].append(b)

        for p in ctx.placements:
            if p.layer not in (1, 2):
                continue
            stack_h = p.cargo.height * p.tier
            x1, x2 = p.x_extent
            y1, y2 = p.y_extent
            affected = self._affected_upper_layers(
                p.layer, stack_h, p.hatch_id, l1, l2, l3)
            for L in affected:
                # (a) Disable overlapping bypass boards on layer L (if any)
                for b in bypass_by_layer.get(L, []):
                    bx1, by1, bx2, by2 = b.polygon.bbox
                    if rects_overlap(x1, y1, x2, y2,
                                     bx1, by1, bx2, by2, strict=True):
                        coupled.append((p.pid, b.board_id))
                # (b) Block upper-layer cargoes whose footprint overlaps
                for q in upper_by_layer.get(L, []):
                    if q.pid == p.pid:
                        continue
                    qx1, qx2 = q.x_extent
                    qy1, qy2 = q.y_extent
                    if rects_overlap(x1, y1, x2, y2,
                                     qx1, qy1, qx2, qy2, strict=True):
                        a, b = sorted((p.pid, q.pid))
                        body_pairs.append((a, b))
        # Deduplicate body_pairs (a low p1 might appear via several layers)
        body_pairs = list(set(body_pairs))
        return coupled, body_pairs
