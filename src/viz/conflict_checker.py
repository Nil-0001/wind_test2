def _footprint(p):
    cargo = getattr(p, "cargo", None)
    length = getattr(p, "length", getattr(cargo, "length", 0))
    width = getattr(p, "width", getattr(cargo, "width", 0))
    sx = length if p.direction == 1 else width
    sy = width if p.direction == 1 else length
    return p.x, p.y, p.x + sx, p.y + sy


def _extract_placements(result):
    placements = getattr(result, "selected_placements", None)
    if placements is not None:
        return list(placements)
    placements = getattr(result, "placements", None)
    if placements is not None:
        return list(placements)
    return []


def _set_no(p, default_idx: int) -> int:
    return int(getattr(p, "set_no", getattr(p, "pid", default_idx)))


def _component_no(p) -> int:
    if hasattr(p, "component_no"):
        return int(p.component_no)
    cargo = getattr(p, "cargo", None)
    return int(getattr(cargo, "component_no", 0))


def check_conflicts(result):
    issues = []
    placements = _extract_placements(result)
    for i in range(len(placements)):
        a = placements[i]
        ax0, ay0, ax1, ay1 = _footprint(a)
        for j in range(i + 1, len(placements)):
            b = placements[j]
            if a.layer != b.layer:
                continue
            bx0, by0, bx1, by1 = _footprint(b)
            x_overlap = (ax0 < bx1 + 500) and (bx0 < ax1 + 500)
            y_overlap = (ay0 < by1 + 100) and (by0 < ay1 + 100)
            if not (x_overlap and y_overlap):
                continue
            issues.append(
                {
                    "type": "spacing",
                    "layer": a.layer,
                    "a_index": i,
                    "b_index": j,
                    "a_set": _set_no(a, i + 1),
                    "a_component": _component_no(a),
                    "b_set": _set_no(b, j + 1),
                    "b_component": _component_no(b),
                    "a_bbox": (ax0, ay0, ax1, ay1),
                    "b_bbox": (bx0, by0, bx1, by1),
                }
            )
    return issues
