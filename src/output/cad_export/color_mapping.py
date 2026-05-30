"""Load and resolve component color mapping."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_ACI = [1, 2, 3, 4, 5, 6, 30, 210, 24, 44, 94, 130, 170]
DECK_ACI = 140


def load_color_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        return {}
    return data


def resolve_color(component_no: int, mapping: dict[str, Any]) -> int | str:
    value = mapping.get(str(component_no))
    if isinstance(value, int):
        return _avoid_deck_color(_sanitize_aci(value))
    if isinstance(value, str):
        if value.startswith("#"):
            return value
        if value.isdigit():
            return _avoid_deck_color(_sanitize_aci(int(value)))
    idx = component_no % len(DEFAULT_ACI)
    return _avoid_deck_color(DEFAULT_ACI[idx])


def _sanitize_aci(color_index: int) -> int:
    if color_index < 1:
        return 1
    if color_index > 255:
        return 255
    return color_index


def _avoid_deck_color(color_index: int) -> int:
    if color_index == DECK_ACI:
        return 5
    return color_index
