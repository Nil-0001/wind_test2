"""Constraint 8: each Layer 2/3 placement consumes its supporting bypass boards
(forces z[b]=1) and the total enabled bypass boards must be ≤ 18.
"""
from __future__ import annotations

import pyomo.environ as pyo

from .base import ConstraintBase, ModelContext

MAX_BYPASS = 18


class C08BypassLimit(ConstraintBase):
    name = "C08_bypass_limit"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        # 8(a) Aggregate bypass count
        m.c8_total_bypass = pyo.Constraint(
            expr=sum(ctx.z[b.board_id] for b in ctx.bypass_boards) <= MAX_BYPASS
        )

        # 8(b) Each Layer 2/3 placement implies its supporting boards are enabled.
        link_pairs: list[tuple[int, str]] = []
        users_by_board: dict[str, list[int]] = {}
        for p in ctx.placements:
            if p.layer not in (2, 3):
                continue
            for bid in p.supporting_boards:
                if bid in ctx.bypass_by_id:
                    link_pairs.append((p.pid, bid))
                    users_by_board.setdefault(bid, []).append(p.pid)

        m.set_c8_links = pyo.Set(initialize=link_pairs, dimen=2)

        def rule(model, pid, bid):
            return ctx.y[pid] <= ctx.z[bid]

        m.c8_bypass_link = pyo.Constraint(m.set_c8_links, rule=rule)

        # 8(c) Reverse: z[b] = 0 unless some y[p] uses b.
        # z[b] <= sum(y[p]) over its users; if no users, force z[b] = 0.
        def rule_no_spurious(model, bid):
            users = users_by_board.get(bid, [])
            if not users:
                return ctx.z[bid] == 0
            return ctx.z[bid] <= sum(ctx.y[u] for u in users)

        m.c8_no_spurious = pyo.Constraint(
            [b.board_id for b in ctx.bypass_boards],
            rule=rule_no_spurious,
        )
