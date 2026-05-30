"""Constraint 10: uniform-load capacity per board ≤ 3 t/m².

For each enabled board b, the sum of half-weight contributions of placements
resting on b, divided by board area, must not exceed 3 t/m².

Linearised:  Σ_p half_weight(p) · 1{b in supporting_boards(p)} · y[p]
              ≤ 3 · area_m2(b) · z[b]
where z[b] is forced to 1 if any selected p uses b (Constraint 8 ensures this
for bypass boards; for hatch covers we treat them as always usable, with z=1).
"""
from __future__ import annotations

import pyomo.environ as pyo

from .base import ConstraintBase, ModelContext

LIMIT_T_PER_M2 = 3.0


class C10LoadCapacity(ConstraintBase):
    name = "C10_load_capacity"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        bypass_ids = list(ctx.bypass_by_id.keys())
        hatch_ids = list(ctx.hatch_by_id.keys())

        # Index placements by board
        loads_by_board: dict[str, list[int]] = {bid: [] for bid in bypass_ids + hatch_ids}
        for p in ctx.placements:
            for bid in p.supporting_boards:
                if bid in loads_by_board:
                    loads_by_board[bid].append(p.pid)

        # Bypass boards: z[b] gates capacity
        bypass_active = [bid for bid in bypass_ids if loads_by_board[bid]]
        m.set_c10_bypass = pyo.Set(initialize=bypass_active)

        def rule_bypass(model, bid):
            board = ctx.bypass_by_id[bid]
            cap = LIMIT_T_PER_M2 * board.polygon.area_m2
            load = sum(ctx.placements_by_id[pid].half_weight * ctx.y[pid]
                       for pid in loads_by_board[bid])
            return load <= cap * ctx.z[bid]

        m.c10_bypass_load = pyo.Constraint(m.set_c10_bypass, rule=rule_bypass)

        # Hatch covers: always available, fixed capacity (no z var)
        hatch_active = [bid for bid in hatch_ids if loads_by_board[bid]]
        m.set_c10_hatch = pyo.Set(initialize=hatch_active)

        def rule_hatch(model, bid):
            cover = ctx.hatch_by_id[bid]
            cap = LIMIT_T_PER_M2 * cover.polygon.area_m2
            load = sum(ctx.placements_by_id[pid].half_weight * ctx.y[pid]
                       for pid in loads_by_board[bid])
            return load <= cap

        m.c10_hatch_load = pyo.Constraint(m.set_c10_hatch, rule=rule_hatch)
