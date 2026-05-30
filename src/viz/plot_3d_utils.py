import plotly.graph_objects as go

LAYER_GAP_Z = 6000.0
COMP_COLORS = {
    1: "#1f77b4",
    2: "#ff7f0e",
    3: "#2ca02c",
    4: "#d62728",
    5: "#9467bd",
    6: "#8c564b",
}


def ensure_closed(points):
    pts = list(points)
    if not pts:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def signed_area(points):
    pts = ensure_closed(points)
    if len(pts) < 4:
        return 0.0
    area = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def ensure_clockwise(points):
    pts = ensure_closed(points)
    if signed_area(pts) > 0:
        core = pts[:-1]
        core.reverse()
        return ensure_closed(core)
    return pts


def box_vertices(x0, y0, z0, x1, y1, z1):
    return (
        [x0, x1, x1, x0, x0, x1, x1, x0],
        [y0, y0, y1, y1, y0, y0, y1, y1],
        [z0, z0, z0, z0, z1, z1, z1, z1],
    )


def box_mesh_triangles():
    """12 triangles covering all 6 faces of the cube.

    Vertex layout (matches box_vertices):
        0=(x0,y0,z0) 1=(x1,y0,z0) 2=(x1,y1,z0) 3=(x0,y1,z0)   [bottom]
        4=(x0,y0,z1) 5=(x1,y0,z1) 6=(x1,y1,z1) 7=(x0,y1,z1)   [top]

    Faces (each as 2 tris): bottom 0-1-2,0-2-3; top 4-5-6,4-6-7;
    front 0-1-5,0-5-4; back 3-2-6,3-6-7; left 0-3-7,0-7-4; right 1-2-6,1-6-5.
    """
    return (
        [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1],
        [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6],
        [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5],
    )


def box_edges(x0, y0, z0, x1, y1, z1):
    pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs.extend([pts[a][0], pts[b][0], None])
        ys.extend([pts[a][1], pts[b][1], None])
        zs.extend([pts[a][2], pts[b][2], None])
    return xs, ys, zs


def enabled_bypass_set(result) -> set:
    enabled = getattr(result, "enabled_bypass", None)
    if enabled is None:
        enabled = []
        for b in getattr(result, "enabled_bypass_boards", []) or []:
            enabled.append(getattr(b, "board_id", b))
    return set(enabled)


def add_boards(fig, vessel, enabled_bypass: set) -> None:
    """Render bypass boards (L2/L3) and hatch covers (L4) as flat panels."""
    if vessel is None:
        return
    for b in getattr(vessel, "bypass_boards", ()):
        pts = ensure_clockwise(getattr(b.polygon, "points", ()))
        if len(pts) < 4:
            continue
        z = (b.layer - 1) * LAYER_GAP_Z
        is_on = b.board_id in enabled_bypass
        edge = "rgba(0,150,40,0.95)" if is_on else "rgba(120,120,120,0.55)"
        fill = "rgba(70,180,90,0.30)" if is_on else "rgba(190,190,190,0.18)"
        x = [p[0] for p in pts]; y = [p[1] for p in pts]
        fig.add_trace(go.Mesh3d(
            x=x[:-1], y=y[:-1], z=[z]*4, i=[0,0], j=[1,2], k=[2,3],
            color=fill, opacity=0.55, showscale=False,
            name=f"Bypass L{b.layer}-H{b.hatchno}-{b.label}",
            legendgroup="boards", showlegend=False,
            hovertemplate=f"Bypass L{b.layer}-H{b.hatchno}-{b.label}"
                          f"<br>{'enabled' if is_on else 'unused'}<extra></extra>",
        ))
        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=[z]*len(x), mode="lines",
            line=dict(color=edge, width=3 if is_on else 1.5),
            showlegend=False, hoverinfo="skip",
        ))
    for c in getattr(vessel, "hatch_covers", ()):
        pts = ensure_clockwise(getattr(c.polygon, "points", ()))
        if len(pts) < 4:
            continue
        z = 3 * LAYER_GAP_Z
        x = [p[0] for p in pts]; y = [p[1] for p in pts]
        fig.add_trace(go.Mesh3d(
            x=x[:-1], y=y[:-1], z=[z]*4, i=[0,0], j=[1,2], k=[2,3],
            color="rgba(160,160,160,0.18)", opacity=0.4, showscale=False,
            name=f"HatchCover-{c.label}", legendgroup="boards", showlegend=False,
            hovertemplate=f"HatchCover {c.label}<extra></extra>",
        ))
        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=[z]*len(x), mode="lines",
            line=dict(color="rgba(110,110,110,0.6)", width=1.5),
            showlegend=False, hoverinfo="skip",
        ))


def iter_placements(result):
    if hasattr(result, "placements"):
        for p in result.placements:
            cargo = getattr(p, "cargo", None)
            yield {
                "set_no": int(getattr(p, "set_no", getattr(p, "pid", 0))),
                "component_no": int(getattr(p, "component_no", getattr(cargo, "component_no", 0))),
                "layer": int(getattr(p, "layer", 1)),
                "direction": int(getattr(p, "direction", 1)),
                "tier": int(getattr(p, "tier", 1)),
                "x": float(getattr(p, "x", 0.0)),
                "y": float(getattr(p, "y", 0.0)),
                "length": float(getattr(p, "length", getattr(cargo, "length", 0.0))),
                "width": float(getattr(p, "width", getattr(cargo, "width", 0.0))),
                "height": float(getattr(p, "height", getattr(cargo, "height", 0.0))),
                "weight": float(getattr(p, "weight", getattr(cargo, "weight", 0.0))),
            }
        return
    if hasattr(result, "selected_placements"):
        for p in result.selected_placements:
            cargo = getattr(p, "cargo", None)
            yield {
                "set_no": int(getattr(p, "set_no", getattr(p, "pid", 0))),
                "component_no": int(getattr(p, "component_no", getattr(cargo, "component_no", 0))),
                "layer": int(getattr(p, "layer", 1)),
                "direction": int(getattr(p, "direction", 1)),
                "tier": int(getattr(p, "tier", 1)),
                "x": float(getattr(p, "x", 0.0)),
                "y": float(getattr(p, "y", 0.0)),
                "length": float(getattr(p, "length", getattr(cargo, "length", 0.0))),
                "width": float(getattr(p, "width", getattr(cargo, "width", 0.0))),
                "height": float(getattr(p, "height", getattr(cargo, "height", 0.0))),
                "weight": float(getattr(p, "weight", getattr(cargo, "weight", 0.0))),
            }
        return
    for idx, c in enumerate(result.get("cargoPosition", []), start=1):
        p1 = c["coordinate"]["1"]
        yield {
            "set_no": idx,
            "component_no": int(c["componentNo"]),
            "layer": int(c["Layer"]),
            "direction": int(c["direction"]),
            "tier": int(c["tier"]),
            "x": float(p1["x"]),
            "y": float(p1["y"]),
            "length": float(c["length"]),
            "width": float(c["width"]),
            "height": float(c["height"]),
            "weight": float(c["weight"]),
        }
