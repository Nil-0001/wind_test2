"""Write the solution to a JSON file in the format specified in prompt.md."""
from __future__ import annotations

import json
from pathlib import Path

from ..core.data_models import BypassBoard, Placement
from ..solver.result_extractor import SolutionView


def to_json_dict(view: SolutionView) -> dict:
    out: dict = {
        "totalSetCount": view.total_set_count,
        "cargoPosition": [_placement_to_dict(p) for p in view.placements],
        "bypassBoardPosition": [_bypass_to_dict(b) for b in view.enabled_bypass_boards],
    }
    return out


def write_json(view: SolutionView, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(to_json_dict(view), f, ensure_ascii=False, indent=2)
    return p


def _placement_to_dict(p: Placement) -> dict:
    corners = p.corners
    return {
        "cargoType": p.cargo.cargo_type,
        "cargoName": p.cargo.cargo_name,
        "componentNo": p.cargo.component_no,
        "cargoLabel": p.cargo.cargo_label,
        "length": p.cargo.length,
        "width": p.cargo.width,
        "height": p.cargo.height,
        "weight": p.cargo.weight,
        "Layer": p.layer,
        "coordinate": {
            "1": _xyz(*corners["1"]),
            "2": _xyz(*corners["2"]),
            "3": _xyz(*corners["3"]),
            "4": _xyz(*corners["4"]),
        },
        "tier": p.tier,
        "direction": p.direction,
    }


def _bypass_to_dict(b: BypassBoard) -> dict:
    pts = b.polygon.points
    return {
        "1": _xyz(*pts[0]),
        "2": _xyz(*pts[1]),
        "3": _xyz(*pts[2]),
        "4": _xyz(*pts[3]),
        "layer": b.layer,
        "hatchno": b.hatchno,
        "label": b.label,
    }


def _xyz(x: float, y: float, z: float = 0.0) -> dict:
    return {"x": x, "y": y, "z": z}
