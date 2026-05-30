"""Layer 2 / 3 candidate generation: corners must rest on bypass boards."""
from __future__ import annotations

import math

from .candidate_layer1 import extents
from .data_models import BypassBoard, Placement
from .geometry import min_height_over_x_range, rect_in_polygon


def gen_layer23(cargo, layer: int, boards, feasible, counter, y_gap: int,
                x_phases: int = 1, y_phases: int = 1):
    out: list[Placement] = []
    fr_by_hatch = {fr.hatch_id: fr for fr in feasible}
    boards_by_hatch: dict[int, list[BypassBoard]] = {}
    for b in boards:
        boards_by_hatch.setdefault(b.hatchno, []).append(b)

    for hatchno, hboards in boards_by_hatch.items():
        fr = fr_by_hatch.get(f"Hatch{hatchno}")
        if fr is None:
            continue
        sorted_x = sorted(hboards, key=lambda b: b.polygon.bbox[0])
        for direction in (1, 0):
            tiers = (1, 2) if direction == 1 else (1,)
            xs, ys = extents(cargo, direction)
            if direction == 1:
                out.extend(_gen_along(cargo, layer, sorted_x, fr, counter,
                                      tiers, xs, ys, y_gap,
                                      x_phases, y_phases))
            else:
                out.extend(_gen_athwart(cargo, layer, sorted_x, fr, counter,
                                        tiers, xs, ys, y_gap,
                                        x_phases, y_phases))
    return out


def _gen_along(cargo, layer, boards, fr, counter, tiers, xs, ys, y_gap,
               x_phases, y_phases):
    """direction=1: cargo length spans (one or) two boards along x.

    The cargo's left end (x = cx) must lie inside the left board's x range, and
    the right end (x = cx + xs) inside the right board's x range. We snap the
    candidate's BL/BR points strictly to the inside of each polygon (ceil/floor)
    to avoid floating-point off-by-one issues. x_phases controls how many
    anchors we sample inside each (L,R) cx-range; y_phases offsets the y slot
    grid.
    """
    out = []
    for i, lboard in enumerate(boards):
        lx1, ly1, lx2, ly2 = lboard.polygon.bbox
        for j in range(i, len(boards)):
            rboard = boards[j]
            rx1, ry1, rx2, ry2 = rboard.polygon.bbox
            # cx must satisfy: BL/TL inside L (lx1 <= cx <= lx2)
            #                 AND BR/TR inside R (rx1 <= cx+xs <= rx2)
            cx_low = max(_ceil_int(lx1), _ceil_int(rx1) - xs)
            cx_high = min(_floor_int(lx2), _floor_int(rx2) - xs)
            if cx_low > cx_high:
                continue
            cx_choices = _spread(cx_low, cx_high, x_phases)
            for cx in cx_choices:
                ry_lo = max(_ceil_int(ly1), _ceil_int(ry1))
                ry_hi = min(_floor_int(ly2), _floor_int(ry2)) - ys
                if ry_lo > ry_hi:
                    continue
                y_step = ys + y_gap
                for cy in _y_anchors(ry_lo, ry_hi, y_step, y_phases):
                    if not _corners_on_two_boards(cx, cy, xs, ys, lboard, rboard):
                        continue
                    if not rect_in_polygon(cx, cy, cx + xs, cy + ys, fr.polygon):
                        continue
                    boards_used = (lboard.board_id,) if lboard.board_id == rboard.board_id \
                        else (lboard.board_id, rboard.board_id)
                    for tier in tiers:
                        if layer == 3 and not _layer3_height_ok(cargo, fr, cx, cx + xs, tier):
                            continue
                        out.append(Placement(
                            pid=next(counter), cargo=cargo, layer=layer,
                            x=cx, y=cy, direction=1, tier=tier,
                            supporting_boards=boards_used,
                            hatch_id=fr.hatch_id,
                        ))
    return out


def _ceil_int(v: float) -> int:
    return int(math.ceil(v))


def _floor_int(v: float) -> int:
    return int(math.floor(v))


def _spread(lo: int, hi: int, n_phases: int) -> list[int]:
    """Sample n_phases+1 evenly spaced integers in [lo, hi].

    n_phases=1 reproduces the previous behaviour: just the two endpoints
    (or a single point if lo == hi). Larger n_phases inserts intermediate
    anchors. Result is deduplicated and sorted.
    """
    if lo >= hi:
        return [lo]
    n = max(1, int(n_phases))
    if n == 1:
        return [lo, hi]
    step = (hi - lo) / n
    pts = sorted({int(round(lo + i * step)) for i in range(n + 1)})
    return [max(lo, min(hi, p)) for p in pts]


def _y_anchors(lo: int, hi: int, y_step: int, n_phases: int) -> list[int]:
    """Generate y anchors at every y_step starting from each phase offset."""
    if lo > hi:
        return []
    n = max(1, int(n_phases))
    out: set[int] = set()
    for ph in range(n):
        y_off = (y_step // n) * ph
        for cy in range(lo + y_off, hi + 1, y_step):
            out.add(cy)
    return sorted(out)


def _corners_on_two_boards(cx, cy, xs, ys, lboard, rboard) -> bool:
    """Verify BL/TL on lboard and BR/TR on rboard (strict point-in-poly)."""
    from .geometry import point_in_polygon
    bl, tl = (cx, cy), (cx, cy + ys)
    br, tr = (cx + xs, cy), (cx + xs, cy + ys)
    return (
        point_in_polygon(*bl, lboard.polygon)
        and point_in_polygon(*tl, lboard.polygon)
        and point_in_polygon(*br, rboard.polygon)
        and point_in_polygon(*tr, rboard.polygon)
    )


def _gen_athwart(cargo, layer, boards, fr, counter, tiers, xs, ys, y_gap,
                 x_phases, y_phases):
    """direction=0: cargo length is along y. Cargo width can fit on a single
    board OR straddle two adjacent boards (BL/TL on left, BR/TR on right).
    Mirrors _gen_along structurally; the `i==j` case keeps single-board.
    """
    out = []
    for i, lboard in enumerate(boards):
        lx1, ly1, lx2, ly2 = lboard.polygon.bbox
        for j in range(i, len(boards)):
            rboard = boards[j]
            rx1, ry1, rx2, ry2 = rboard.polygon.bbox
            cx_low = max(_ceil_int(lx1), _ceil_int(rx1) - xs)
            cx_high = min(_floor_int(lx2), _floor_int(rx2) - xs)
            if cx_low > cx_high:
                continue
            cx_choices = _spread(cx_low, cx_high, x_phases)
            for cx in cx_choices:
                ry_lo = max(_ceil_int(ly1), _ceil_int(ry1))
                ry_hi = min(_floor_int(ly2), _floor_int(ry2)) - ys
                if ry_lo > ry_hi:
                    continue
                y_step = ys + y_gap
                for cy in _y_anchors(ry_lo, ry_hi, y_step, y_phases):
                    if not _corners_on_two_boards(cx, cy, xs, ys, lboard, rboard):
                        continue
                    if not rect_in_polygon(cx, cy, cx + xs, cy + ys, fr.polygon):
                        continue
                    boards_used = (lboard.board_id,) if lboard.board_id == rboard.board_id \
                        else (lboard.board_id, rboard.board_id)
                    for tier in tiers:
                        if layer == 3 and not _layer3_height_ok(cargo, fr, cx, cx + xs, tier):
                            continue
                        out.append(Placement(
                            pid=next(counter), cargo=cargo, layer=layer,
                            x=cx, y=cy, direction=0, tier=tier,
                            supporting_boards=boards_used,
                            hatch_id=fr.hatch_id,
                        ))
    return out


def _layer3_height_ok(cargo, fr, cx1, cx2, tier) -> bool:
    if fr.height_segments is None:
        return True
    needed = cargo.height * tier
    return min_height_over_x_range(cx1, cx2, fr.height_segments) >= needed
