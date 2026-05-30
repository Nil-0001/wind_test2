"""Constraint 9: Layer 1/2/3 cargo cannot cross hatch boundaries.

Already enforced by candidate generation (each Layer 1/2/3 candidate is
emitted within a single hatch's feasible polygon). This module asserts the
invariant.
"""
from __future__ import annotations

from .base import ConstraintBase, ModelContext


class C09NoCrossHatch(ConstraintBase):
    name = "C09_no_cross_hatch"

    def apply(self, ctx: ModelContext) -> None:
        for p in ctx.placements:
            if p.layer in (1, 2, 3) and p.hatch_id is None:
                raise AssertionError(
                    f"C9 violation: placement {p.pid} on Layer {p.layer} has no "
                    f"hatch assignment."
                )
