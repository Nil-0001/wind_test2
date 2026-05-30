"""Layer 4 candidate generation: top deck above hatch covers."""
from __future__ import annotations

from .candidate_layer1 import extents
from .data_models import Placement, VesselStructure
from .geometry import point_in_polygon, rect_in_polygon


def gen_layer4(cargo, vessel: VesselStructure, fr, counter,
               y_gap: int, x_gap: int, x_phases: int, y_phases: int):
    out: list[Placement] = []
    x_min, y_min, x_max, y_max = (int(v) for v in fr.polygon.bbox)
    boards = list(vessel.hatch_covers)
    for direction in (1, 0):
        tiers = (1, 2) if direction == 1 else (1,)
        xs, ys = extents(cargo, direction)
        if xs > (x_max - x_min) or ys > (y_max - y_min):
            continue
        x_step = xs + x_gap
        y_step = ys + y_gap
        for xp in range(x_phases):
            x_off = (x_step // x_phases) * xp if x_phases else 0
            for yp in range(y_phases):
                y_off = (y_step // y_phases) * yp if y_phases else 0
                for x in range(x_min + x_off, x_max - xs + 1, x_step):
                    for y in range(y_min + y_off, y_max - ys + 1, y_step):
                        if not rect_in_polygon(x, y, x + xs, y + ys, fr.polygon):
                            continue
                        supports = _corners_on_boards(x, y, x + xs, y + ys, boards)
                        if not supports:
                            continue
                        for tier in tiers:
                            out.append(Placement(
                                pid=next(counter), cargo=cargo, layer=4,
                                x=x, y=y, direction=direction, tier=tier,
                                supporting_boards=tuple(sorted(set(supports))),
                                hatch_id=None,
                            ))
    return out


def _corners_on_boards(x1, y1, x2, y2, boards) -> list[str]:
    corners = ((x1, y1), (x1, y2), (x2, y2), (x2, y1))
    covered: list[str] = []
    for cx, cy in corners:
        ok_id = None
        for b in boards:
            if point_in_polygon(cx, cy, b.polygon):
                ok_id = b.board_id
                break
        if ok_id is None:
            return []
        covered.append(ok_id)
    return covered
