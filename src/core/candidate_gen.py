"""Top-level candidate generation orchestrator.

Delegates to per-layer modules; keeps this file thin so per-layer logic stays
in dedicated files (candidate_layer1.py, candidate_layer23.py, candidate_layer4.py).
"""
from __future__ import annotations

from itertools import count

from .candidate_layer1 import gen_layer1
from .candidate_layer23 import gen_layer23
from .candidate_layer4 import gen_layer4
from .data_models import Placement, ProblemData


def gen_candidates(problem: ProblemData,
                   y_gap: int = 100,
                   x_gap: int = 500,
                   layer1_x_phases: int = 3,
                   layer1_y_phases: int = 2,
                   layer23_x_phases: int = 2,
                   layer23_y_phases: int = 2,
                   layer4_x_phases: int = 2,
                   layer4_y_phases: int = 3) -> list[Placement]:
    cargoes_flat = [c for cs in problem.cargoes_by_type.values() for c in cs]
    counter = count()
    out: list[Placement] = []

    fr_layer = {1: [], 2: [], 3: [], 4: []}
    for fr in problem.vessel.feasible_ranges:
        fr_layer[fr.layer].append(fr)

    bypass_layer = {2: [], 3: []}
    for b in problem.vessel.bypass_boards:
        bypass_layer[b.layer].append(b)

    for cargo in cargoes_flat:
        for fr in fr_layer[1]:
            out.extend(gen_layer1(cargo, fr, counter, y_gap, x_gap,
                                  layer1_x_phases, layer1_y_phases))
        for layer in (2, 3):
            out.extend(gen_layer23(cargo, layer, bypass_layer[layer],
                                   fr_layer[layer], counter, y_gap,
                                   layer23_x_phases, layer23_y_phases))
        if fr_layer[4]:
            out.extend(gen_layer4(cargo, problem.vessel, fr_layer[4][0],
                                  counter, y_gap, x_gap,
                                  layer4_x_phases, layer4_y_phases))
    return out


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from pathlib import Path
    from .data_loader import load_problem
    p = Path(__file__).resolve().parents[2] / "data" / "test_data.json"
    pd = load_problem(p)
    cands = gen_candidates(pd)
    print(f"Total candidates: {len(cands)}")
    for layer in (1, 2, 3, 4):
        nl = sum(1 for c in cands if c.layer == layer)
        print(f"  Layer {layer}: {nl}")
    by_cn: dict[int, int] = {}
    for c in cands:
        by_cn[c.cargo.component_no] = by_cn.get(c.cargo.component_no, 0) + 1
    for cn in sorted(by_cn):
        print(f"  componentNo {cn}: {by_cn[cn]}")
