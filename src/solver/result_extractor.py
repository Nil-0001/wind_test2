"""Extract a serialisable solution view from the SolveResult."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.data_models import BypassBoard, Placement
from .pyomo_model import SolveResult


@dataclass
class SolutionView:
    total_set_count: int
    placements: list[Placement]
    enabled_bypass_boards: list[BypassBoard]


def to_view(result: SolveResult, all_bypass: list[BypassBoard]) -> SolutionView:
    by_id = {b.board_id: b for b in all_bypass}
    enabled = [by_id[bid] for bid in result.enabled_bypass if bid in by_id]
    return SolutionView(
        total_set_count=result.total_set_count,
        placements=list(result.selected_placements),
        enabled_bypass_boards=enabled,
    )
