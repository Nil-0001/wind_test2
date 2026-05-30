"""Constraint base interface and shared model context."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import pyomo.environ as pyo

from ..core.data_models import (
    BypassBoard, FeasibleRange, HatchCover, Placement, ProblemData,
)


@dataclass
class ModelContext:
    """Shared bag passed to every constraint's apply() call."""
    problem: ProblemData
    placements: list[Placement]
    placements_by_id: dict[int, Placement] = field(default_factory=dict)
    bypass_boards: list[BypassBoard] = field(default_factory=list)
    bypass_by_id: dict[str, BypassBoard] = field(default_factory=dict)
    hatch_covers: list[HatchCover] = field(default_factory=list)
    hatch_by_id: dict[str, HatchCover] = field(default_factory=dict)
    feasible_ranges: list[FeasibleRange] = field(default_factory=list)
    # Pyomo handles
    model: Optional[Any] = None  # pyo.ConcreteModel
    y: dict[int, Any] = field(default_factory=dict)   # y[pid]
    z: dict[str, Any] = field(default_factory=dict)   # z[board_id]
    S: Optional[Any] = None                            # totalSetCount

    @classmethod
    def from_problem(cls, problem: ProblemData,
                     placements: list[Placement]) -> "ModelContext":
        ctx = cls(problem=problem, placements=placements)
        ctx.placements_by_id = {p.pid: p for p in placements}
        ctx.bypass_boards = list(problem.vessel.bypass_boards)
        ctx.bypass_by_id = {b.board_id: b for b in ctx.bypass_boards}
        ctx.hatch_covers = list(problem.vessel.hatch_covers)
        ctx.hatch_by_id = {c.board_id: c for c in ctx.hatch_covers}
        ctx.feasible_ranges = list(problem.vessel.feasible_ranges)
        return ctx


class ConstraintBase:
    """Each concrete constraint adds its inequalities/equalities to model."""
    name: str = "ConstraintBase"

    def apply(self, ctx: ModelContext) -> None:
        raise NotImplementedError
