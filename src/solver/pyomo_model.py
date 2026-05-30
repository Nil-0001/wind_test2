"""Build and solve the Pyomo MILP for the stowage problem."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pyomo.environ as pyo

from ..constraints.base import ConstraintBase, ModelContext
from ..constraints.c01_direction_tier import C01DirectionTier
from ..constraints.c02_set_integrity import C02SetIntegrity
from ..constraints.c03_lateral_gap import C03LateralGap
from ..constraints.c04_longitudinal_gap import C04LongitudinalGap
from ..constraints.c05_corners_on_board import C05CornersOnBoard
from ..constraints.c06_no_head_to_head import C06NoHeadToHead
from ..constraints.c07_feasible_range import C07FeasibleRange
from ..constraints.c08_bypass_limit import C08BypassLimit
from ..constraints.c09_no_cross_hatch import C09NoCrossHatch
from ..constraints.c10_load_capacity import C10LoadCapacity
from ..core.data_models import Placement, ProblemData


@dataclass
class SolveResult:
    status: str
    obj_value: Optional[float]
    selected_placements: list[Placement]
    enabled_bypass: list[str]
    total_set_count: int


def build_model(problem: ProblemData,
                placements: list[Placement]) -> ModelContext:
    """Construct the Pyomo ConcreteModel and attach decision variables."""
    ctx = ModelContext.from_problem(problem, placements)
    m = pyo.ConcreteModel()
    ctx.model = m

    placement_ids = [p.pid for p in placements]
    bypass_ids = [b.board_id for b in ctx.bypass_boards]
    m.set_pids = pyo.Set(initialize=placement_ids)
    m.set_bypass = pyo.Set(initialize=bypass_ids)
    m.y = pyo.Var(m.set_pids, within=pyo.Binary)
    m.z = pyo.Var(m.set_bypass, within=pyo.Binary)
    m.S = pyo.Var(within=pyo.NonNegativeIntegers, bounds=(0, _hard_upper_bound(placements)))

    ctx.y = {pid: m.y[pid] for pid in placement_ids}
    ctx.z = {bid: m.z[bid] for bid in bypass_ids}
    ctx.S = m.S

    # Objective: maximize total set count
    m.obj = pyo.Objective(expr=m.S, sense=pyo.maximize)

    # Apply constraints
    for cls in (
        C01DirectionTier,
        C02SetIntegrity,
        C03LateralGap,
        C04LongitudinalGap,
        C05CornersOnBoard,
        C06NoHeadToHead,
        C07FeasibleRange,
        C08BypassLimit,
        C09NoCrossHatch,
        C10LoadCapacity,
    ):
        cls().apply(ctx)
    return ctx


def solve(ctx: ModelContext, solver_name: str = "appsi_highs",
          time_limit_s: int = 600,
          tee: bool = True) -> SolveResult:
    solver_name, solver = _select_solver(solver_name)
    _apply_time_limit(solver, solver_name, time_limit_s)
    # APPSI Highs raises if no feasible solution is loaded; we'd rather
    # return an empty result and let the caller handle it.
    try:
        solver.config.load_solution = False
    except Exception:
        pass
    # APPSI doesn't take tee= kwarg; it uses config.stream_solver.
    try:
        solver.config.stream_solver = bool(tee)
    except Exception:
        pass
    try:
        if solver_name in ("appsi_highs", "highs"):
            res = solver.solve(ctx.model)
        else:
            res = solver.solve(ctx.model, tee=tee)
    except RuntimeError as e:
        # Time limit hit before any feasible solution. Return empty.
        return SolveResult(status=f"time_limit_no_solution: {e}",
                           obj_value=None, selected_placements=[],
                           enabled_bypass=[], total_set_count=0)
    status = _extract_status(res)
    # Best feasible (if any). For appsi_highs, this attribute is on the result.
    has_solution = (
        getattr(res, "best_feasible_objective", None) is not None
        or status in ("optimal", "feasible")
    )
    if has_solution:
        try:
            solver.load_vars()  # APPSI requires explicit load when load_solution=False
        except Exception:
            pass
    obj_raw = pyo.value(ctx.model.obj, exception=False)
    obj_val = float(obj_raw) if obj_raw is not None else None
    if obj_val is not None:
        s_raw = pyo.value(ctx.S, exception=False)
        set_count = int(round(s_raw)) if s_raw is not None else 0
    else:
        set_count = 0

    def yv(pid):
        v = pyo.value(ctx.y[pid], exception=False)
        return 0.0 if v is None else v

    def zv(bid):
        v = pyo.value(ctx.z[bid], exception=False)
        return 0.0 if v is None else v

    selected = [p for p in ctx.placements
                if (yv(p.pid) or 0) > 0.5]
    enabled = [bid for bid in ctx.z if (zv(bid) or 0) > 0.5]

    return SolveResult(
        status=status, obj_value=obj_val,
        selected_placements=selected, enabled_bypass=enabled,
        total_set_count=set_count,
    )


def _select_solver(name: str):
    """Try the requested solver; fall back through GLPK -> CBC -> appsi_highs."""
    candidates = [name] + [s for s in ("appsi_highs", "glpk", "cbc") if s != name]
    last_err = None
    for s in candidates:
        try:
            if s in ("appsi_highs", "highs"):
                # Direct APPSI import — the SolverFactory wrapper has buggy
                # time_limit / load_solution forwarding in some pyomo versions.
                from pyomo.contrib.appsi.solvers import Highs
                solver = Highs()
                if solver.available():
                    return s, solver
            else:
                solver = pyo.SolverFactory(s)
                if solver.available(exception_flag=False):
                    return s, solver
        except Exception as e:  # pragma: no cover
            last_err = e
    raise RuntimeError(
        f"No MILP solver available. Tried: {candidates}. Last error: {last_err}"
    )


def _apply_time_limit(solver, name: str, seconds: int) -> None:
    """Belt-and-suspenders: set every channel that might forward to the solver."""
    try:
        if name == "glpk":
            solver.options["tmlim"] = seconds
        elif name == "cbc":
            solver.options["seconds"] = seconds
        elif name in ("appsi_highs", "highs"):
            # Pyomo APPSI top-level config (some versions ignore this).
            try:
                solver.config.time_limit = float(seconds)
            except Exception:
                pass
            # Direct HiGHS option pass-through (this is what actually works).
            try:
                solver.highs_options["time_limit"] = float(seconds)
            except Exception:
                pass
            # Fallback if highspy primitive is exposed.
            try:
                if hasattr(solver, "_solver_model") and solver._solver_model is not None:
                    solver._solver_model.setOptionValue("time_limit", float(seconds))
            except Exception:
                pass
    except Exception:
        pass


def _extract_status(res) -> str:
    try:
        return str(res.solver.termination_condition)
    except Exception:
        try:
            return str(res.termination_condition)
        except Exception:
            return "unknown"


def _hard_upper_bound(placements: list[Placement]) -> int:
    """Loose upper bound on totalSetCount (sum of tier across smallest cn)."""
    counts: dict[int, int] = {}
    for p in placements:
        counts[p.cargo.component_no] = counts.get(p.cargo.component_no, 0) + p.tier
    if not counts:
        return 0
    return max(0, min(counts.values()))
