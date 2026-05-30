"""Constraint 1: direction=0 (athwart) ⇒ tier=1.

Already enforced at candidate-generation time (the layer modules only emit
tier=2 candidates when direction=1). Here we only assert invariants and refuse
to add candidates that violate the rule.
"""
from __future__ import annotations

from .base import ConstraintBase, ModelContext


class C01DirectionTier(ConstraintBase):
    name = "C01_direction_tier"

    def apply(self, ctx: ModelContext) -> None:
        for p in ctx.placements:
            if p.direction == 0 and p.tier != 1:
                raise AssertionError(
                    f"Placement {p.pid} violates C1: direction=0 must imply tier=1, "
                    f"got tier={p.tier}."
                )
            if p.tier not in (1, 2):
                raise AssertionError(f"Placement {p.pid} has invalid tier={p.tier}.")
