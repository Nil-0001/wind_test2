"""3D stowage plot: cargoes (Mesh3d cubes) + boards + layer contours."""
from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from .plot_3d_layers import add_conflict_boxes, add_layer_contours
from .plot_3d_utils import (
    COMP_COLORS,
    LAYER_GAP_Z,
    add_boards,
    box_edges,
    box_mesh_triangles,
    box_vertices,
    enabled_bypass_set,
    iter_placements,
)


def _build_3d_figure(
    result, vessel, conflicts=None,
    enhanced_style: bool = True,
    highlight_conflicts: bool = True,
    show_boards: bool = True,
):
    conflicts = conflicts or []
    fig = go.Figure()
    add_layer_contours(fig, vessel, enhanced_style=enhanced_style)
    if show_boards:
        add_boards(fig, vessel, enabled_bypass_set(result))

    shown_comp: set[int] = set()
    per_layer_count = {1: 0, 2: 0, 3: 0, 4: 0}
    per_layer_weight = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    tri_i, tri_j, tri_k = box_mesh_triangles()

    for p in iter_placements(result):
        sx = p["length"] if p["direction"] == 1 else p["width"]
        sy = p["width"] if p["direction"] == 1 else p["length"]
        x0, y0 = p["x"], p["y"]
        x1, y1 = x0 + sx, y0 + sy
        z_base = (p["layer"] - 1) * LAYER_GAP_Z
        color = COMP_COLORS.get(p["component_no"], "#7f8c8d")
        per_layer_count[p["layer"]] += p["tier"]
        per_layer_weight[p["layer"]] += p["weight"] * p["tier"]

        levels = 2 if p["tier"] == 2 else 1
        for lv in range(levels):
            z0 = z_base + lv * p["height"]
            z1 = z0 + p["height"]
            vx, vy, vz = box_vertices(x0, y0, z0, x1, y1, z1)
            fig.add_trace(go.Mesh3d(
                x=vx, y=vy, z=vz, i=tri_i, j=tri_j, k=tri_k,
                color=color,
                opacity=0.26 if lv == 0 else 0.16,
                flatshading=True,
                name=f"Comp{p['component_no']}",
                legendgroup=f"comp{p['component_no']}",
                showlegend=(p["component_no"] not in shown_comp and lv == 0),
                hovertemplate=(
                    f"Comp={p['component_no']} Set={p['set_no']}<br>"
                    f"Layer={p['layer']} tier={p['tier']} dir={p['direction']}<br>"
                    f"x=[{x0:.0f},{x1:.0f}] y=[{y0:.0f},{y1:.0f}] "
                    f"z=[{z0:.0f},{z1:.0f}]<extra></extra>"
                ),
            ))
            ex, ey, ez = box_edges(x0, y0, z0, x1, y1, z1)
            fig.add_trace(go.Scatter3d(
                x=ex, y=ey, z=ez, mode="lines",
                line=dict(color=color, width=4 if lv == 0 else 2),
                showlegend=False, hoverinfo="skip",
            ))
        shown_comp.add(p["component_no"])

    if highlight_conflicts:
        add_conflict_boxes(fig, conflicts)
    if conflicts:
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            marker=dict(color="red", size=6),
            name=f"Conflicts={len(conflicts)}",
            legendgroup="conflicts", showlegend=True,
        ))

    layer_note = " | ".join(
        f"L{ly}:count={per_layer_count[ly]},wt={per_layer_weight[ly]:.1f}t"
        for ly in (1, 2, 3, 4)
    )
    total_sets = (result.total_set_count if hasattr(result, "total_set_count")
                  else result.get("totalSetCount", 0))
    fig.update_layout(
        title=(f"Stowage 3D | sets={total_sets} | conflicts={len(conflicts)}"
               f"<br><sup>{layer_note}</sup>"),
        scene=dict(xaxis_title="x(mm)", yaxis_title="y(mm)", zaxis_title="z(mm)",
                   aspectmode="data",
                   camera=dict(eye=dict(x=1.5, y=1.35, z=0.8))),
        legend=dict(itemsizing="constant", x=1.02, y=1.0),
        margin=dict(l=5, r=170, t=70, b=10),
        template="plotly_white",
    )
    return fig


def plot_3d(
    result, vessel, output_dir: str | Path,
    conflicts=None,
    enhanced_style: bool = True,
    highlight_conflicts: bool = True,
    show_boards: bool = True,
) -> Path:
    fig = _build_3d_figure(result, vessel, conflicts,
                           enhanced_style, highlight_conflicts, show_boards)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    out_path = out / "stowage_3d.html"
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path


def plot_3d_string(
    result, vessel, conflicts=None,
    enhanced_style: bool = True,
    highlight_conflicts: bool = True,
    show_boards: bool = True,
) -> str:
    """Return the 3D stowage plot as a self-contained HTML string."""
    fig = _build_3d_figure(result, vessel, conflicts,
                           enhanced_style, highlight_conflicts, show_boards)
    return fig.to_html(include_plotlyjs="cdn", full_html=True)
