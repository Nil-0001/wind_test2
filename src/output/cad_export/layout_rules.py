"""Compute CAD draw layout from source data and solve results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CargoRect:
    layer: int
    component_no: int
    cargo_name: str
    cargo_type: str
    cargo_label: str
    length: float
    width: float
    height: float
    weight: float
    tier: int
    direction: int
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class LayerBoundary:
    layer: int
    hatch_id: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class DeckBoard:
    kind: str
    layer: int
    label: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class LayoutModel:
    cargo_rects: list[CargoRect]
    boundaries: list[LayerBoundary]
    deck_boards: list[DeckBoard]
    layer_step: float


def build_layout_model(test_data: dict[str, Any], result_dict: dict[str, Any]) -> LayoutModel:
    cargo_items = list(result_dict.get("cargoPosition", []))
    raw_bounds = _extract_layer_boundaries(test_data)
    raw_boards = _extract_deck_boards(test_data, result_dict)
    min_y, max_y = _y_range(cargo_items, raw_bounds, raw_boards)
    step = max(1.0, (max_y - min_y) + 1200.0)
    boundaries = [_shift_boundary(b, step) for b in raw_bounds]
    deck_boards = [_shift_board(board, step) for board in raw_boards]
    cargo_rects = [_cargo_rect(item, step) for item in cargo_items]
    return LayoutModel(cargo_rects=cargo_rects, boundaries=boundaries, deck_boards=deck_boards, layer_step=step)


def _extract_layer_boundaries(test_data: dict[str, Any]) -> list[LayerBoundary]:
    ranges = test_data.get("vesselStructure", {}).get("stowageFeasibleRange", {})
    out: list[LayerBoundary] = []
    for layer in (1, 2, 3, 4):
        key = f"Layer{layer}"
        layer_raw = ranges.get(key)
        if not layer_raw:
            continue
        if layer == 4:
            points = _coord_points(layer_raw)
            out.append(LayerBoundary(layer=4, hatch_id="Layer4", points=points))
            continue
        for hatch_id, hatch_value in layer_raw.items():
            if not hatch_id.startswith("Hatch"):
                continue
            out.append(LayerBoundary(layer=layer, hatch_id=hatch_id, points=_coord_points(hatch_value)))
    return out


def _coord_points(raw: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    keys = sorted([k for k in raw.keys() if k.isdigit()], key=int)
    return tuple((float(raw[k]["x"]), float(raw[k]["y"])) for k in keys)


def _extract_deck_boards(test_data: dict[str, Any], result_dict: dict[str, Any]) -> list[DeckBoard]:
    vessel = test_data.get("vesselStructure", {})
    bypass_raw = result_dict.get("bypassBoardPosition", [])
    hatch_raw = vessel.get("hatchCoverPosition", [])
    boards: list[DeckBoard] = []
    for item in bypass_raw:
        boards.append(
            DeckBoard(
                kind="bypass",
                layer=int(item.get("layer", 1)),
                label=f"BYPASS_L{item.get('layer', 1)}_H{item.get('hatchno', 0)}_{item.get('label', 0)}",
                points=_coord_points(item),
            )
        )
    for item in hatch_raw:
        boards.append(
            DeckBoard(
                kind="hatch_cover",
                layer=4,
                label=f"HATCH_COVER_{item.get('label', 0)}",
                points=_coord_points(item),
            )
        )
    return boards


def _y_range(
    cargo_items: list[dict[str, Any]],
    boundaries: list[LayerBoundary],
    boards: list[DeckBoard],
) -> tuple[float, float]:
    ys: list[float] = []
    for item in cargo_items:
        for key in ("1", "2", "3", "4"):
            ys.append(float(item["coordinate"][key]["y"]))
    for bound in boundaries:
        ys.extend(p[1] for p in bound.points)
    for board in boards:
        ys.extend(p[1] for p in board.points)
    if not ys:
        return 0.0, 1000.0
    return min(ys), max(ys)


def _cargo_rect(item: dict[str, Any], step: float) -> CargoRect:
    layer = int(item.get("Layer", 1))
    shifted = tuple(
        (
            float(item["coordinate"][key]["x"]),
            float(item["coordinate"][key]["y"]) + _layer_offset(layer, step),
        )
        for key in ("1", "2", "3", "4")
    )
    return CargoRect(
        layer=layer,
        component_no=int(item.get("componentNo", 0)),
        cargo_name=str(item.get("cargoName", "")),
        cargo_type=str(item.get("cargoType", "")),
        cargo_label=str(item.get("cargoLabel", "")),
        length=float(item.get("length", 0)),
        width=float(item.get("width", 0)),
        height=float(item.get("height", 0)),
        weight=float(item.get("weight", 0)),
        tier=int(item.get("tier", 1)),
        direction=int(item.get("direction", 1)),
        points=shifted,
    )


def _shift_boundary(boundary: LayerBoundary, step: float) -> LayerBoundary:
    shifted = tuple((x, y + _layer_offset(boundary.layer, step)) for x, y in boundary.points)
    return LayerBoundary(layer=boundary.layer, hatch_id=boundary.hatch_id, points=shifted)


def _shift_board(board: DeckBoard, step: float) -> DeckBoard:
    shifted = tuple((x, y + _layer_offset(board.layer, step)) for x, y in board.points)
    return DeckBoard(kind=board.kind, layer=board.layer, label=board.label, points=shifted)


def _layer_offset(layer: int, step: float) -> float:
    return float((layer - 1) * step)
