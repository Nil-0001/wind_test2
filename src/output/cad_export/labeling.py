"""Build fixed-template cargo labels."""
from __future__ import annotations

from .layout_rules import CargoRect


def build_three_line_label(rect: CargoRect) -> tuple[str, str, str]:
    line1 = f"{rect.cargo_type}    {rect.cargo_name}"
    line2 = (
        f"LxBxH={_mm_to_m(rect.length):.2f}x"
        f"{_mm_to_m(rect.width):.2f}x"
        f"{_mm_to_m(rect.height):.2f}m"
    )
    line3 = f"Weight={_format_weight(rect.weight)}t"
    return (line1, line2, line3)


def rect_center(rect: CargoRect) -> tuple[float, float]:
    xs = [p[0] for p in rect.points]
    ys = [p[1] for p in rect.points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def rect_bbox(rect: CargoRect) -> tuple[float, float, float, float]:
    xs = [p[0] for p in rect.points]
    ys = [p[1] for p in rect.points]
    return (min(xs), min(ys), max(xs), max(ys))


def _mm_to_m(value_mm: float) -> float:
    return value_mm / 1000.0


def _format_weight(weight: float) -> str:
    text = f"{weight:.2f}"
    if text.endswith("00"):
        return text[:-3]
    if text.endswith("0"):
        return text[:-1]
    return text
