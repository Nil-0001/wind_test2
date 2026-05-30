"""Write CAD DXF from computed layout."""
from __future__ import annotations

from pathlib import Path

import ezdxf

from .labeling import build_three_line_label, rect_bbox, rect_center
from .layout_rules import LayoutModel

DECK_BLUE_ACI = 140
LABEL_HEIGHT = 200.0
LABEL_GAP = 150.0
TIER_BADGE_HEIGHT = 220.0
TIER_BADGE_COLOR = 1


def write_dxf(layout: LayoutModel, output_path: Path, color_of_component: dict[int, int | str]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2010")
    doc.units = 4  # millimeter
    msp = doc.modelspace()
    _ensure_base_layers(doc)
    _draw_boundaries(msp, layout)
    _draw_cargo(msp, layout, doc, color_of_component)
    doc.saveas(output_path)
    return output_path


def _ensure_base_layers(doc: ezdxf.EzDxf) -> None:
    if "BOUNDARY" not in doc.layers:
        doc.layers.add("BOUNDARY", color=8)
    if "BYPASS" not in doc.layers:
        doc.layers.add("BYPASS", color=DECK_BLUE_ACI)
    if "HATCH_COVER" not in doc.layers:
        doc.layers.add("HATCH_COVER", color=DECK_BLUE_ACI)


def _draw_boundaries(msp, layout: LayoutModel) -> None:
    for boundary in layout.boundaries:
        points = list(boundary.points) + [boundary.points[0]]
        msp.add_lwpolyline(points, dxfattribs={"layer": "BOUNDARY", "lineweight": 15})
    _draw_deck_boards(msp, layout)


def _draw_cargo(msp, layout: LayoutModel, doc, color_of_component: dict[int, int | str]) -> None:
    for rect in layout.cargo_rects:
        layer_name = _component_layer(doc, rect.component_no, color_of_component.get(rect.component_no))
        points = list(rect.points) + [rect.points[0]]
        msp.add_lwpolyline(points, dxfattribs={"layer": layer_name, "lineweight": 25})
        _draw_cargo_text(msp, rect, layer_name)


def _draw_deck_boards(msp, layout: LayoutModel) -> None:
    for board in layout.deck_boards:
        layer_name = "BYPASS" if board.kind == "bypass" else "HATCH_COVER"
        points = list(board.points) + [board.points[0]]
        msp.add_lwpolyline(points, dxfattribs={"layer": layer_name, "lineweight": 20})
        

def _draw_cargo_text(msp, rect, layer_name: str) -> None:
    line1, line2, line3 = build_three_line_label(rect)
    cx, cy = rect_center(rect)
    rotation = 0.0 if rect.direction == 1 else 90.0
    if rect.direction == 1:
        p1 = (cx, cy + LABEL_GAP)
        p2 = (cx, cy)
        p3 = (cx, cy - LABEL_GAP)
    else:
        p1 = (cx - LABEL_GAP, cy)
        p2 = (cx, cy)
        p3 = (cx + LABEL_GAP, cy)
    _add_center_text(msp, line1, p1, layer_name, rotation)
    _add_center_text(msp, line2, p2, layer_name, rotation)
    _add_center_text(msp, line3, p3, layer_name, rotation)
    if rect.tier == 2:
        _add_tier_badge(msp, rect, layer_name)


def _add_center_text(msp, text: str, point: tuple[float, float], layer_name: str, rotation: float) -> None:
    msp.add_text(
        text,
        dxfattribs={"height": LABEL_HEIGHT, "layer": layer_name, "rotation": rotation},
    ).set_placement(point, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _add_tier_badge(msp, rect, layer_name: str) -> None:
    x1, y1, x2, y2 = rect_bbox(rect)
    if rect.direction == 1:
        point = (x2 - 250.0, y2 - 250.0)
    else:
        point = (x1 + 250.0, y2 - 250.0)
    msp.add_text(
        "TIER=2",
        dxfattribs={
            "height": TIER_BADGE_HEIGHT,
            "layer": layer_name,
            "color": TIER_BADGE_COLOR,
            "rotation": 0.0,
        },
    ).set_placement(point, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _component_layer(doc, component_no: int, color: int | str | None) -> str:
    layer_name = f"COMP_{component_no}"
    if layer_name in doc.layers:
        return layer_name
    kwargs = {}
    if isinstance(color, int):
        kwargs["color"] = color
    doc.layers.add(layer_name, **kwargs)
    if isinstance(color, str) and color.startswith("#"):
        doc.layers.get(layer_name).rgb = _hex_to_rgb(color)
    return layer_name


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    raw = color.lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    if len(raw) != 6:
        return (255, 255, 255)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
