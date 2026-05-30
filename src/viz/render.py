"""Compose 4-layer subplots into a single HTML; optionally export PNGs."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..core.data_models import ProblemData
from ..solver.result_extractor import SolutionView
from .layer_plot import _COMPONENT_COLORS, add_layer_traces


_LAYER_TITLES = {
    1: "Layer 1 — In-hatch (no bypass)",
    2: "Layer 2 — On Layer-2 bypass boards",
    3: "Layer 3 — On Layer-3 bypass boards",
    4: "Layer 4 — Top deck (on hatch covers)",
}


def _build_visualization_figure(problem: ProblemData, view: SolutionView):
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=tuple(_LAYER_TITLES[i] for i in (1, 2, 3, 4)),
        horizontal_spacing=0.06, vertical_spacing=0.10,
    )
    enabled = {b.board_id for b in view.enabled_bypass_boards}
    pos = {1: (1, 1), 2: (1, 2), 3: (2, 1), 4: (2, 2)}
    for layer, (r, c) in pos.items():
        add_layer_traces(fig, r, c, layer, problem, view.placements, enabled)

    fig.update_layout(
        title=dict(text=_build_title(problem, view), font=dict(size=15)),
        height=1200, width=1700, plot_bgcolor="#fafafa",
        margin=dict(t=140, l=60, r=240, b=60), showlegend=False,
    )
    for r, c in pos.values():
        fig.update_xaxes(title="x (mm)", row=r, col=c, gridcolor="rgba(0,0,0,0.07)")
        fig.update_yaxes(title="y (mm)", row=r, col=c,
                         scaleanchor=f"x{(r-1)*2+c}", scaleratio=1,
                         gridcolor="rgba(0,0,0,0.07)")
    _add_legend(fig, view)
    return fig


def render_html(problem: ProblemData, view: SolutionView,
                out_path: str | Path) -> Path:
    fig = _build_visualization_figure(problem, view)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out), include_plotlyjs="cdn")
    return out


def render_html_string(problem: ProblemData, view: SolutionView) -> str:
    """Return the layered visualization as a self-contained HTML string."""
    return _build_visualization_figure(problem, view).to_html(
        include_plotlyjs="cdn", full_html=True)


def export_layer_pngs(problem: ProblemData, view: SolutionView,
                      out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    enabled = {b.board_id for b in view.enabled_bypass_boards}
    for layer in (1, 2, 3, 4):
        fig = make_subplots(rows=1, cols=1)
        add_layer_traces(fig, 1, 1, layer, problem, view.placements, enabled)
        n_layer = sum(1 for p in view.placements if p.layer == layer)
        fig.update_layout(
            title=f"{_LAYER_TITLES[layer]}  |  cargoes on this layer: {n_layer}",
            showlegend=False, width=1600, height=720,
            margin=dict(t=70, l=60, r=200, b=60), plot_bgcolor="#fafafa",
        )
        fig.update_xaxes(title="x (mm)", gridcolor="rgba(0,0,0,0.07)")
        fig.update_yaxes(title="y (mm)", scaleanchor="x", scaleratio=1,
                         gridcolor="rgba(0,0,0,0.07)")
        _add_legend(fig, view, single_layer=layer)
        path = out_dir / f"layer{layer}.png"
        try:
            fig.write_image(str(path))
            saved.append(path)
        except Exception:
            pass
    return saved


# ---------------------------------------------------------------------------
# Title and legend builders
# ---------------------------------------------------------------------------
def _build_title(problem: ProblemData, view: SolutionView) -> str:
    n_per_cn = Counter(p.cargo.component_no for p in view.placements)
    units_per_cn = Counter()
    for p in view.placements:
        units_per_cn[p.cargo.component_no] += p.tier
    layer_counts = Counter(p.layer for p in view.placements)
    layer_str = " · ".join(f"L{i}: {layer_counts.get(i, 0)}" for i in (1, 2, 3, 4))
    cargo_units = ", ".join(f"#{cn}={units_per_cn[cn]}u/{n_per_cn[cn]}p"
                            for cn in sorted(units_per_cn))
    bypass_count = len(view.enabled_bypass_boards)
    return (
        f"<b>Wind Stowage Plan — totalSetCount = {view.total_set_count}</b><br>"
        f"<sup>Placements: {len(view.placements)} ({layer_str}) · "
        f"Bypass enabled: {bypass_count}/18 · "
        f"per-component (units/placements): {cargo_units}</sup>"
    )


def _add_legend(fig: go.Figure, view: SolutionView, single_layer: int = 0) -> None:
    """Manual legend on the right side: colors per componentNo + tier markers."""
    items: list[tuple[str, str]] = []
    for cn in range(1, 7):
        col = _COMPONENT_COLORS[(cn - 1) % len(_COMPONENT_COLORS)]
        items.append((col, f"componentNo {cn}"))
    items.append(("#666", "─── tier=1 (single)"))
    items.append(("#666", "═══ tier=2 (×2 stacked)"))
    items.append(("#1f8a3c", "■ bypass enabled"))
    items.append(("#a0a0a0", "□ bypass disabled"))
    items.append(("#888", "→ direction=1 (顺船)"))
    items.append(("#888", "↑ direction=0 (横船)"))

    legend_text = "<br>".join(
        f"<span style='color:{col}'>●</span> {label}"
        for col, label in items
    )
    fig.add_annotation(
        x=1.0, y=1.0, xref="paper", yref="paper",
        xanchor="left", yanchor="top",
        text="<b>Legend</b><br>" + legend_text,
        showarrow=False, align="left",
        font=dict(size=11, color="#222"),
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="rgba(120,120,120,0.6)", borderwidth=1, borderpad=8,
    )
