"""Layer-contour, polygon-fill and conflict-box renderers for plot_3d."""
from __future__ import annotations

import plotly.graph_objects as go

from .plot_3d_utils import LAYER_GAP_Z, ensure_clockwise


_LAYER_STYLE = {
    1: {"line": "rgba(35,35,35,0.85)", "width": 6, "fill": "rgba(150,150,150,0.12)"},
    2: {"line": "rgba(50,50,50,0.80)", "width": 5, "fill": "rgba(170,170,170,0.10)"},
    3: {"line": "rgba(70,70,70,0.75)", "width": 4, "fill": "rgba(185,185,185,0.09)"},
    4: {"line": "rgba(90,90,90,0.70)", "width": 4, "fill": "rgba(205,205,205,0.08)"},
}


def _poly_points(reg):
    pts = ensure_clockwise(getattr(reg.polygon, "points", ()))
    return pts if len(pts) >= 4 else []


def _poly_area_m2(points):
    if len(points) < 4:
        return 0.0
    area2 = 0.0
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        area2 += x1 * y2 - x2 * y1
    return abs(area2 * 0.5) / 1_000_000.0


def _add_polygon_fill(fig, x, y, z, layer, reg_key):
    style = _LAYER_STYLE.get(layer, _LAYER_STYLE[4])
    if len(x) == 5:
        fig.add_trace(go.Mesh3d(
            x=x[:-1], y=y[:-1], z=[z] * 4, i=[0, 0], j=[1, 2], k=[2, 3],
            color=style["fill"], opacity=0.35, showscale=False,
            name=f"Layer{layer} plane", legendgroup=f"layer{layer}",
            showlegend=False, hoverinfo="skip",
        ))
        return
    fig.add_trace(go.Scatter3d(
        x=x, y=y, z=[z] * len(x), mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=1),
        surfaceaxis=2, surfacecolor=style["fill"], opacity=0.35,
        name=f"Layer{layer} plane", legendgroup=f"layer{layer}",
        showlegend=False,
        hovertemplate=f"Layer {layer} region fill<br>{reg_key}<extra></extra>",
    ))


def add_layer_contours(fig, vessel, enhanced_style: bool = True) -> None:
    if vessel is None:
        return
    for layer in (1, 2, 3, 4):
        style = _LAYER_STYLE.get(layer, _LAYER_STYLE[4]) if enhanced_style else _LAYER_STYLE[4]
        z = (layer - 1) * LAYER_GAP_Z
        for reg in getattr(vessel, "feasible_ranges", ()):
            if getattr(reg, "layer", None) != layer:
                continue
            pts = _poly_points(reg)
            if not pts:
                continue
            reg_key = reg.hatch_id or f"L{layer}"
            area_m2 = _poly_area_m2(pts)
            x = [p[0] for p in pts]; y = [p[1] for p in pts]
            fig.add_trace(go.Scatter3d(
                x=x, y=y, z=[z] * len(x), mode="lines",
                line=dict(color=style["line"], width=style["width"] if enhanced_style else 4),
                name=f"Layer{layer} contour", legendgroup=f"layer{layer}",
                showlegend=False,
                hovertemplate=(
                    f"Layer {layer} contour<br>{reg_key}<br>"
                    f"area={area_m2:.2f} m2<extra></extra>"
                ),
            ))
            _add_polygon_fill(fig, x, y, z, layer, reg_key)
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            marker=dict(size=1, color="rgba(0,0,0,0)"),
            name=f"Layer{layer}", legendgroup=f"layer{layer}", showlegend=True,
        ))


def add_conflict_boxes(fig, conflicts) -> None:
    if not conflicts:
        return
    seen = set()
    for it in conflicts:
        layer = int(it.get("layer", 0))
        if layer <= 0:
            continue
        z = (layer - 1) * LAYER_GAP_Z + 40.0
        for key in ("a_bbox", "b_bbox"):
            box = it.get(key)
            if not box:
                continue
            x0, y0, x1, y1 = map(float, box)
            box_key = (layer, round(x0, 2), round(y0, 2),
                       round(x1, 2), round(y1, 2))
            if box_key in seen:
                continue
            seen.add(box_key)
            xs = [x0, x1, x1, x0, x0]
            ys = [y0, y0, y1, y1, y0]
            fig.add_trace(go.Scatter3d(
                x=xs, y=ys, z=[z] * len(xs), mode="lines",
                line=dict(color="rgba(220,53,69,0.95)", width=7),
                name="Conflict bbox", legendgroup="conflicts",
                showlegend=False,
                hovertemplate=(
                    f"Conflict layer={layer}<br>"
                    f"x=[{x0:.0f},{x1:.0f}] y=[{y0:.0f},{y1:.0f}]<extra></extra>"
                ),
            ))
