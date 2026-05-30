"""Post-hoc constraint verification on the produced result.json.

Run after main.py:    python -m src.verify
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .core.data_loader import load_problem
from .core.geometry import (
    intervals_overlap, point_in_polygon, rects_overlap,
    min_height_over_x_range,
)


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    data = base / "data" / "test_data.json"
    result_path = base / "output" / "result.json"
    with result_path.open(encoding="utf-8") as f:
        result = json.load(f)
    problem = load_problem(data)
    placements = [_normalize(p) for p in result["cargoPosition"]]
    enabled = [b for b in result["bypassBoardPosition"]]

    fails: list[str] = []
    fails.extend(check_c1(placements))
    fails.extend(check_c2(result, placements))
    fails.extend(check_c34(placements))
    fails.extend(check_c5(placements, problem))
    fails.extend(check_c8(enabled, placements, problem))
    fails.extend(check_c10(placements, problem))

    if fails:
        print("Constraint check FAILED:")
        for f in fails[:30]:
            print(" -", f)
        return 1
    print(f"All checks PASSED. totalSetCount={result['totalSetCount']} "
          f"(placements={len(placements)}, enabled bypass={len(enabled)}).")
    return 0


def _normalize(p):
    cs = p["coordinate"]
    xs = [cs[k]["x"] for k in ("1", "2", "3", "4")]
    ys = [cs[k]["y"] for k in ("1", "2", "3", "4")]
    return {**p, "x_lo": min(xs), "x_hi": max(xs),
            "y_lo": min(ys), "y_hi": max(ys)}


def check_c1(ps):
    out = []
    for p in ps:
        if p["direction"] == 0 and p["tier"] != 1:
            out.append(f"C1: pid {p['cargoName']} dir=0 tier={p['tier']}")
    return out


def check_c2(result, ps):
    out = []
    counts = {}
    for p in ps:
        counts[p["componentNo"]] = counts.get(p["componentNo"], 0) + p["tier"]
    s = result["totalSetCount"]
    for cn, c in counts.items():
        if c < s:
            out.append(f"C2: cn={cn} count={c} < S={s}")
    return out


def check_c34(ps):
    out = []
    by_layer: dict[int, list] = {}
    for p in ps:
        by_layer.setdefault(p["Layer"], []).append(p)
    for layer, lst in by_layer.items():
        for i in range(len(lst)):
            a = lst[i]
            for j in range(i + 1, len(lst)):
                b = lst[j]
                x_over = intervals_overlap(a["x_lo"], a["x_hi"], b["x_lo"], b["x_hi"], strict=True)
                y_over = intervals_overlap(a["y_lo"], a["y_hi"], b["y_lo"], b["y_hi"], strict=True)
                if x_over and not y_over:
                    gap = max(a["y_lo"], b["y_lo"]) - min(a["y_hi"], b["y_hi"])
                    if gap < 100:
                        out.append(f"C3: layer {layer} pair {a['cargoName']} & {b['cargoName']} y-gap={gap}")
                if y_over and not x_over:
                    gap = max(a["x_lo"], b["x_lo"]) - min(a["x_hi"], b["x_hi"])
                    if gap < 500:
                        out.append(f"C4: layer {layer} pair {a['cargoName']} & {b['cargoName']} x-gap={gap}")
                if x_over and y_over:
                    out.append(f"C3/4: layer {layer} OVERLAP {a['cargoName']} & {b['cargoName']}")
    return out


def check_c5(ps, problem):
    out = []
    bypass = problem.vessel.bypass_boards
    hatches = problem.vessel.hatch_covers
    for p in ps:
        if p["Layer"] == 1:
            continue
        for k in ("1", "2", "3", "4"):
            cx, cy = p["coordinate"][k]["x"], p["coordinate"][k]["y"]
            ok = False
            if p["Layer"] in (2, 3):
                for b in bypass:
                    if b.layer == p["Layer"] and point_in_polygon(cx, cy, b.polygon):
                        ok = True
                        break
            else:  # Layer 4
                for b in list(hatches) + list(bypass):
                    if point_in_polygon(cx, cy, b.polygon):
                        ok = True
                        break
            if not ok:
                out.append(f"C5: pid {p['cargoName']} L{p['Layer']} corner {k} ({cx},{cy}) off-board")
    return out


def check_c8(enabled, ps, problem):
    out = []
    if len(enabled) > 18:
        out.append(f"C8: enabled bypass count={len(enabled)} > 18")
    return out


def check_c10(ps, problem):
    out = []
    bypass_id_map = {f"L{b.layer}-H{b.hatchno}-{b.label}": b for b in problem.vessel.bypass_boards}
    hatch_id_map = {f"HC-{c.label}": c for c in problem.vessel.hatch_covers}
    # Approximate which boards each placement rests on by re-computing supporting boards
    # We rely on corner-based detection (same as c05).
    loads: dict[str, float] = {bid: 0.0 for bid in list(bypass_id_map) + list(hatch_id_map)}
    for p in ps:
        if p["Layer"] == 1:
            continue
        bids = set()
        for k in ("1", "2", "3", "4"):
            cx, cy = p["coordinate"][k]["x"], p["coordinate"][k]["y"]
            for bid, b in bypass_id_map.items():
                if b.layer == p["Layer"] and point_in_polygon(cx, cy, b.polygon):
                    bids.add(bid); break
            else:
                for bid, b in hatch_id_map.items():
                    if point_in_polygon(cx, cy, b.polygon):
                        bids.add(bid); break
        half_w = (p["weight"] * p["tier"]) / 2.0
        for bid in bids:
            loads[bid] += half_w
    for bid, w in loads.items():
        if w == 0:
            continue
        b = bypass_id_map.get(bid) or hatch_id_map.get(bid)
        cap = 3.0 * b.polygon.area_m2
        if w > cap + 1e-6:
            out.append(f"C10: board {bid} load={w:.2f}t > cap={cap:.2f}t")
    return out


if __name__ == "__main__":
    sys.exit(main())
