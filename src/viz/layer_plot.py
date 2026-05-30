"""Build a single-layer Plotly figure with rich annotations.

Each cargo shows: componentNo · tier badge · direction arrow.
Tier=2 cargoes get thicker borders and a contrasting inner stripe.
Bypass boards show their label; enabled boards are tinted green.
"""
from __future__ import annotations

from typing import Iterable

import plotly.graph_objects as go

from ..core.data_models import Placement, ProblemData

# Distinct hue per componentNo (1..6)
_COMPONENT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c",
    "#d62728", "#9467bd", "#8c564b",
]


def add_layer_traces(fig: go.Figure, row: int, col: int,
                     layer: int, problem: ProblemData,
                     placements: list[Placement],
                     enabled_bypass: set[str]) -> None:
    _draw_feasible(fig, row, col, layer, problem)
    _draw_boards(fig, row, col, layer, problem, enabled_bypass)
    _draw_cargoes(fig, row, col, layer, placements)


# ---------------------------------------------------------------------------
# Feasible range polygons (background)
# ---------------------------------------------------------------------------
def _draw_feasible(fig, row, col, layer, problem):
    for fr in problem.vessel.feasible_ranges:
        if fr.layer != layer:
            continue
        _add_polygon(fig, fr.polygon.points, row, col,
                     fillcolor="rgba(225,235,250,0.55)",
                     line_color="rgba(70,110,170,0.6)",
                     line_width=1,
                     hovertext=f"Feasible {fr.hatch_id or 'L4'}")


# ---------------------------------------------------------------------------
# Hatch covers / bypass boards
# ---------------------------------------------------------------------------
def _draw_boards(fig, row, col, layer, problem, enabled_bypass):
    if layer == 4:
        for c in problem.vessel.hatch_covers:
            _add_polygon(fig, c.polygon.points, row, col,
                         fillcolor="rgba(190,190,190,0.30)",
                         line_color="rgba(110,110,110,0.7)",
                         line_width=1,
                         hovertext=f"HC-{c.label}")
            cx, cy = _centroid(c.polygon.points)
            _add_text(fig, cx, cy, f"HC{c.label}", row, col,
                      color="rgba(80,80,80,0.8)", size=9)

    if layer in (2, 3):
        for b in problem.vessel.bypass_boards:
            if b.layer != layer:
                continue
            enabled = b.board_id in enabled_bypass
            _add_polygon(
                fig, b.polygon.points, row, col,
                fillcolor=("rgba(70,180,90,0.30)" if enabled else "rgba(190,190,190,0.18)"),
                line_color=("rgba(0,110,30,1.0)" if enabled else "rgba(160,160,160,0.55)"),
                line_width=(2 if enabled else 1),
                hovertext=f"L{b.layer}-H{b.hatchno}-{b.label}" + (" (ON)" if enabled else ""),
            )
            cx, cy = _centroid(b.polygon.points)
            _add_text(fig, cx, cy, f"#{b.label}", row, col,
                      color=("rgba(0,90,30,0.95)" if enabled else "rgba(140,140,140,0.85)"),
                      size=9)


# ---------------------------------------------------------------------------
# Cargo placements
# ---------------------------------------------------------------------------
def _draw_cargoes(fig, row, col, layer, placements):
    for p in placements:
        if p.layer != layer:
            continue
        x1, x2 = p.x_extent
        y1, y2 = p.y_extent
        color = _COMPONENT_COLORS[(p.cargo.component_no - 1) % len(_COMPONENT_COLORS)]
        # Outer rectangle
        _add_polygon(
            fig, ((x1, y1), (x1, y2), (x2, y2), (x2, y1)), row, col,
            fillcolor=_alpha(color, 0.55 if p.tier == 1 else 0.75),
            line_color=color,
            line_width=2 if p.tier == 1 else 4,
            dash="dot" if p.tier == 2 else None,
            hovertext=_hover(p),
        )
        # Inner stripe for tier=2 (visual cue: stacked × 2)
        if p.tier == 2:
            mid_y = (y1 + y2) / 2
            _add_polygon(
                fig,
                ((x1 + 30, mid_y - 60), (x1 + 30, mid_y + 60),
                 (x2 - 30, mid_y + 60), (x2 - 30, mid_y - 60)),
                row, col,
                fillcolor=_alpha(color, 0.95),
                line_color=color,
                line_width=0,
                hovertext="tier=2 stack",
            )
        # Center label
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        arrow = "→" if p.direction == 1 else "↑"
        tier_tag = "·×2" if p.tier == 2 else ""
        label = f"#{p.cargo.component_no}{tier_tag} {arrow}"
        _add_text(fig, cx, cy, label, row, col,
                  color="white", size=12, bold=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _add_polygon(fig, points, row, col, fillcolor, line_color,
                 line_width=1, dash=None, hovertext=None):
    pts = list(points) + [points[0]]
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    line = dict(color=line_color, width=line_width)
    if dash:
        line["dash"] = dash
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="lines", fill="toself",
            fillcolor=fillcolor, line=line,
            text=hovertext or "", hoverinfo="text",
            showlegend=False,
        ),
        row=row, col=col,
    )


def _add_text(fig, x, y, text, row, col, color="black", size=10, bold=False):
    fig.add_trace(
        go.Scatter(
            x=[x], y=[y], mode="text",
            text=[f"<b>{text}</b>" if bold else text],
            textfont=dict(color=color, size=size),
            hoverinfo="skip", showlegend=False,
        ),
        row=row, col=col,
    )


def _centroid(points: Iterable[tuple[float, float]]):
    pts = list(points)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy


def _hover(p: Placement) -> str:
    x1, x2 = p.x_extent
    y1, y2 = p.y_extent
    sup = ", ".join(p.supporting_boards) if p.supporting_boards else "—"
    return (
        f"<b>{p.cargo.cargo_name}</b> (componentNo={p.cargo.component_no})<br>"
        f"Layer {p.layer} · direction={p.direction} ({'顺船' if p.direction==1 else '横船'}) · tier={p.tier}<br>"
        f"x:[{x1},{x2}] y:[{y1},{y2}] · h_total={p.total_height}mm<br>"
        f"weight={p.cargo.weight}t · supports={sup}"
    )


def _alpha(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a:.2f})"
