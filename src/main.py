"""Entry point: load → generate candidates → solve → write JSON → render HTML."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .core.candidate_gen import gen_candidates
from .core.data_loader import load_problem
from .output.cad_export.service import cad_export_service
from .output.result_writer import to_json_dict
from .output.result_writer import write_json
from .solver.pyomo_model import build_model, solve
from .solver.result_extractor import to_view
from .viz.conflict_checker import check_conflicts
from .viz.plot_3d import plot_3d
from .viz.render import export_layer_pngs, render_html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    base = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Wind power stowage solver")
    p.add_argument("--data", default=str(base / "data" / "test_data.json"))
    p.add_argument("--result", default=str(base / "output" / "result.json"))
    p.add_argument("--html", default=str(base / "output" / "visualization.html"))
    p.add_argument("--png-dir", default=str(base / "output"))
    p.add_argument("--dxf-dir", default=str(base / "output"))
    p.add_argument("--solver", default="appsi_highs",
                   help="Pyomo solver name (appsi_highs / glpk / cbc)")
    p.add_argument("--time-limit", type=int, default=3600)
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log = (lambda *a, **k: None) if args.quiet else print

    log("[1/5] Loading problem data ...")
    t0 = time.time()
    problem = load_problem(args.data)
    log(f"  loaded {sum(len(v) for v in problem.cargoes_by_type.values())} cargoes; "
        f"{len(problem.vessel.bypass_boards)} bypass; "
        f"{len(problem.vessel.hatch_covers)} hatch covers; "
        f"{len(problem.vessel.feasible_ranges)} feasible regions")

    log("[2/5] Generating candidate placements ...")
    placements = gen_candidates(problem)
    log(f"  candidates: {len(placements)}  "
        f"(L1={_count(placements, 1)} L2={_count(placements, 2)} "
        f"L3={_count(placements, 3)} L4={_count(placements, 4)})")

    log("[3/5] Building Pyomo model ...")
    ctx = build_model(problem, placements)

    log(f"[4/5] Solving (solver={args.solver}, time-limit={args.time_limit}s) ...")
    result = solve(ctx, solver_name=args.solver,
                   time_limit_s=args.time_limit, tee=not args.quiet)
    log(f"  status={result.status}  totalSetCount={result.total_set_count}  "
        f"selected={len(result.selected_placements)}  "
        f"enabled bypass={len(result.enabled_bypass)}")

    log("[5/5] Writing outputs ...")
    view = to_view(result, list(problem.vessel.bypass_boards))
    json_path = write_json(view, args.result)
    log(f"  wrote {json_path}")
    html_path = render_html(problem, view, args.html)
    issues = check_conflicts(result)
    out_dir = Path(args.result).resolve().parent
    plot3d_path = plot_3d(result, problem.vessel, out_dir, conflicts=issues)
    log(f"  wrote {html_path}")
    log(f"  wrote {plot3d_path}")
    dxf_path = _export_dxf(args.data, view, args.dxf_dir)
    if dxf_path is not None:
        log(f"  wrote {dxf_path}")
    log(f"  conflicts detected: {len(issues)}")
    pngs = export_layer_pngs(problem, view, args.png_dir)
    if pngs:
        log(f"  wrote {len(pngs)} PNG(s) to {args.png_dir}")

    log(f"\nDone in {time.time() - t0:.1f}s. totalSetCount = {result.total_set_count}")
    return 0


def _count(plist, layer: int) -> int:
    return sum(1 for p in plist if p.layer == layer)


def _export_dxf(data_path: str, view, dxf_dir: str) -> Path | None:
    try:
        test_data = json.loads(Path(data_path).read_text(encoding="utf-8"))
        result_dict = to_json_dict(view)
        color_map = Path(__file__).resolve().parents[1] / "data" / "component_colors.json"
        exported = cad_export_service.export(
            test_data,
            result_dict,
            output_dir=Path(dxf_dir),
            color_map_path=color_map,
        )
        return exported.path
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
