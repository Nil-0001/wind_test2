"""Layer 1 candidate generation: free placement inside hatch polygons."""
from __future__ import annotations

from .data_models import Placement
from .geometry import rect_in_polygon


def extents(cargo, direction: int) -> tuple[int, int]:
    return (cargo.length, cargo.width) if direction == 1 else (cargo.width, cargo.length)


def gen_layer1(cargo, fr, counter, y_gap: int, x_gap: int,
               x_phases: int, y_phases: int) -> list[Placement]:
    out: list[Placement] = []
    x_min, y_min, x_max, y_max = (int(v) for v in fr.polygon.bbox)
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
                        for tier in tiers:
                            out.append(Placement(
                                pid=next(counter), cargo=cargo, layer=1,
                                x=x, y=y, direction=direction, tier=tier,
                                supporting_boards=(), hatch_id=fr.hatch_id,
                            ))
    return out
