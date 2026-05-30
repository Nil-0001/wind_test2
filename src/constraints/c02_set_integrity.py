"""Constraint 2: complete-set requirement.

For each cargo type, totalSetCount S must satisfy
    Σ_{p: cn(p)=k} tier(p) · y[p] ≥ S      ∀ k ∈ {1..6}
The objective is then max S, so the optimum equals min_k (count_k).
"""
from __future__ import annotations

import pyomo.environ as pyo

from .base import ConstraintBase, ModelContext


class C02SetIntegrity(ConstraintBase):
    name = "C02_set_integrity"

    def apply(self, ctx: ModelContext) -> None:
        m = ctx.model
        # Group placements by (cargo_type, component_no)
        groups: dict[tuple[str, int], list[int]] = {}
        for p in ctx.placements:
            key = (p.cargo.cargo_type, p.cargo.component_no)
            groups.setdefault(key, []).append(p.pid)

        cargo_types = sorted({k[0] for k in groups.keys()})
        all_components = sorted({k[1] for k in groups.keys()})

        m.set_components = pyo.Set(initialize=all_components)
        m.set_cargo_types = pyo.Set(initialize=cargo_types)

        def rule(model, ct, k):
            pids = groups.get((ct, k), [])
            if not pids:
                # Whole component absent — forces S = 0
                return ctx.S == 0
            tier_terms = sum(ctx.placements_by_id[pid].tier * ctx.y[pid] for pid in pids)
            return tier_terms >= ctx.S

        m.c2_set_integrity = pyo.Constraint(
            m.set_cargo_types, m.set_components, rule=rule
        )
