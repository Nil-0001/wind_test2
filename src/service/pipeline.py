"""End-to-end: dict-in → result + 2 HTML strings, with progress streaming."""
from __future__ import annotations

import time
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.candidate_gen import gen_candidates
from ..output.cad_export.service import cad_export_service
from ..core.data_loader import load_problem_from_dict
from ..output.result_writer import to_json_dict
from ..solver.pyomo_model import build_model, solve
from ..solver.result_extractor import to_view
from ..viz.conflict_checker import check_conflicts
from ..viz.plot_3d import plot_3d_string
from ..viz.render import render_html_string
from .progress import Event, ProgressEmitter, _LineSplittingStream


@dataclass
class StowageResult:
    result: dict
    stowage_3d_html: str
    visualization_html: str
    elapsed_seconds: float
    conflicts: list
    cad_file: str | None = None


_DEFAULT_PHASES = dict(
    layer1_x_phases=1, layer1_y_phases=1,
    layer23_x_phases=1, layer23_y_phases=1,
    layer4_x_phases=1, layer4_y_phases=1,
)


def solve_stowage(
    test_data: dict,
    *,
    options: Optional[dict] = None,
    progress_cb: Optional[Callable[[Event], None]] = None,
    time_limit_s: int = 180,
    solver_name: str = "appsi_highs",
) -> StowageResult:
    """Solve a single stowage problem instance.

    Args:
        test_data: parsed JSON, the same shape as `test_data.json`.
        options: dict of overrides; supported keys:
            - "phases": dict of phase params (see gen_candidates)
            - "y_gap", "x_gap": minimum gaps in mm
        progress_cb: callback(Event) for progress / log / result / error.
        time_limit_s: solver wall-clock budget.
        solver_name: pyomo solver name (default appsi_highs).

    Returns: StowageResult bundle.
    """
    options = options or {}
    emit = ProgressEmitter(progress_cb)
    t0 = time.time()
    try:
        ts = time.time()
        emit.log("[1/5] Loading problem data ...")
        emit.progress("load", 0, "Parsing input ...")
        problem = load_problem_from_dict(test_data)
        n_cargoes = sum(len(v) for v in problem.cargoes_by_type.values())
        emit.log(
            f"  loaded {n_cargoes} cargoes; "
            f"{len(problem.vessel.bypass_boards)} bypass; "
            f"{len(problem.vessel.hatch_covers)} hatch covers; "
            f"{len(problem.vessel.feasible_ranges)} feasible regions"
        )
        emit.progress(
            "load", 5,
            f"Loaded {n_cargoes} cargoes, "
            f"{len(problem.vessel.bypass_boards)} bypass, "
            f"{len(problem.vessel.hatch_covers)} hatch covers "
            f"[{time.time()-ts:.1f}s]")

        ts = time.time()
        emit.log("[2/5] Generating candidate placements ...")
        emit.progress("candidates", 10, "Generating candidates ...")
        phases = {**_DEFAULT_PHASES, **(options.get("phases") or {})}
        gap = {"y_gap": options.get("y_gap", 100),
               "x_gap": options.get("x_gap", 500)}
        ps = gen_candidates(problem, **gap, **phases)
        l1, l2, l3, l4 = _layer_counts(ps)
        emit.log(f"  candidates: {len(ps)}  (L1={l1} L2={l2} L3={l3} L4={l4})")
        emit.progress("candidates", 25,
                      f"Generated {len(ps)} candidate placements "
                      f"[{time.time()-ts:.1f}s]")

        ts = time.time()
        emit.log("[3/5] Building Pyomo model ...")
        emit.progress("build", 30, "Building MILP model ...")
        ctx = build_model(problem, ps)
        n_constraints = sum(
            len(getattr(ctx.model, name))
            for name in ("set_c3_pairs", "set_c4_pairs", "set_c6_pairs",
                         "set_c7_couples", "set_c7_body", "set_c8_links")
            if hasattr(ctx.model, name))
        emit.progress("build", 50,
                      f"Model ready ({n_constraints} pairwise constraints) "
                      f"[{time.time()-ts:.1f}s]")

        ts = time.time()
        emit.log(f"[4/5] Solving (solver={solver_name}, time-limit={time_limit_s}s) ...")
        emit.progress("solve", 55,
                      f"Solving with {solver_name}, "
                      f"solver_time_limit={time_limit_s}s ...")
        log_stream = _LineSplittingStream(emit)
        with redirect_stdout(log_stream):
            result = solve(ctx, solver_name=solver_name,
                           time_limit_s=time_limit_s, tee=True)
        log_stream.flush()
        emit.progress("solve", 90,
                      f"Solver done: status={result.status} "
                      f"totalSetCount={result.total_set_count} "
                      f"placements={len(result.selected_placements)} "
                      f"bypass={len(result.enabled_bypass)} "
                      f"[{time.time()-ts:.1f}s]")
        emit.log(
            f"  status={result.status} totalSetCount={result.total_set_count} "
            f"selected={len(result.selected_placements)} "
            f"enabled bypass={len(result.enabled_bypass)}"
        )

        ts = time.time()
        emit.log("[5/5] Writing outputs ...")
        emit.progress("output", 92, "Building outputs (JSON + HTML) ...")
        view = to_view(result, list(problem.vessel.bypass_boards))
        result_dict = to_json_dict(view)
        viz_html = render_html_string(problem, view)
        conflicts = check_conflicts(result)
        plot3d_html = plot_3d_string(result, problem.vessel,
                                     conflicts=conflicts)
        cad_file = _export_cad(test_data, result_dict, emit)
        emit.progress("output", 99, f"Outputs ready [{time.time()-ts:.1f}s]")
        emit.log(f"  conflicts detected: {len(conflicts)}")

        elapsed = time.time() - t0
        emit.progress("done", 100, f"Done in {elapsed:.1f}s total")
        emit.log(f"Done in {elapsed:.1f}s. totalSetCount = {result.total_set_count}")

        bundle = StowageResult(
            result=result_dict,
            stowage_3d_html=plot3d_html,
            visualization_html=viz_html,
            elapsed_seconds=elapsed,
            conflicts=conflicts,
            cad_file=str(cad_file) if cad_file else None,
        )
        emit.result({
            "result": result_dict,
            "stowage_3d_html": plot3d_html,
            "visualization_html": viz_html,
            "elapsed_seconds": elapsed,
            "conflicts_count": len(conflicts),
            "cad_available": cad_file is not None,
            "cad_download_url": "/download/cad/latest",
            "cad_file": str(cad_file) if cad_file else None,
        })
        return bundle
    except Exception as exc:  # noqa: BLE001
        emit.error(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        raise


def _export_cad(test_data: dict, result_dict: dict, emit: ProgressEmitter) -> Path | None:
    base_dir = Path(__file__).resolve().parents[2]
    out_dir = base_dir / "output"
    color_map = base_dir / "data" / "component_colors.json"
    try:
        exported = cad_export_service.export(
            test_data,
            result_dict,
            output_dir=out_dir,
            color_map_path=color_map,
        )
        emit.log(f"CAD exported: {exported.path.name}")
        return exported.path
    except Exception as exc:  # noqa: BLE001
        emit.log(f"CAD export skipped: {exc}")
        return None


def _layer_counts(placements: list) -> tuple[int, int, int, int]:
    return tuple(sum(1 for p in placements if p.layer == layer) for layer in (1, 2, 3, 4))
