"""Domain data models for cargoes, vessel structures, and placements."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Polygon:
    """Polygon defined by a tuple of (x, y) points (clockwise from bottom-left)."""
    points: tuple[tuple[float, float], ...]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def area_mm2(self) -> float:
        n = len(self.points)
        s = 0.0
        for i in range(n):
            x1, y1 = self.points[i]
            x2, y2 = self.points[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return abs(s) * 0.5

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / 1_000_000.0


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Cargo:
    cargo_type: str
    cargo_name: str
    component_no: int
    cargo_label: str
    length: int
    width: int
    height: int
    weight: float


# ---------------------------------------------------------------------------
# Vessel structure
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BypassBoard:
    layer: int
    hatchno: int
    label: int
    polygon: Polygon

    @property
    def board_id(self) -> str:
        return f"L{self.layer}-H{self.hatchno}-{self.label}"


@dataclass(frozen=True)
class HatchCover:
    label: int
    polygon: Polygon

    @property
    def board_id(self) -> str:
        return f"HC-{self.label}"


@dataclass(frozen=True)
class FeasibleRange:
    layer: int
    hatch_id: Optional[str]            # "Hatch1".."Hatch4"; None for layer 4
    polygon: Polygon
    height_limit: Optional[float] = None             # uniform limit (mm)
    height_segments: Optional[tuple[dict, ...]] = None  # layer3 segments


@dataclass(frozen=True)
class VesselStructure:
    bypass_boards: tuple[BypassBoard, ...]
    hatch_covers: tuple[HatchCover, ...]
    feasible_ranges: tuple[FeasibleRange, ...]


@dataclass(frozen=True)
class ProblemData:
    cargoes_by_type: dict[str, tuple[Cargo, ...]]
    vessel: VesselStructure


# ---------------------------------------------------------------------------
# Placements
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Placement:
    """A concrete candidate placement of a cargo."""
    pid: int
    cargo: Cargo
    layer: int
    x: int
    y: int
    direction: int   # 1 = along ship (length on x), 0 = athwart (length on y)
    tier: int        # 1 or 2
    # Pre-computed metadata
    supporting_boards: tuple[str, ...] = field(default_factory=tuple)
    hatch_id: Optional[str] = None  # "Hatch1".."Hatch4" or None for layer 4

    @property
    def x_extent(self) -> tuple[int, int]:
        if self.direction == 1:
            return (self.x, self.x + self.cargo.length)
        return (self.x, self.x + self.cargo.width)

    @property
    def y_extent(self) -> tuple[int, int]:
        if self.direction == 1:
            return (self.y, self.y + self.cargo.width)
        return (self.y, self.y + self.cargo.length)

    @property
    def total_height(self) -> int:
        return self.cargo.height * self.tier

    @property
    def corners(self) -> dict[str, tuple[int, int]]:
        x1, x2 = self.x_extent
        y1, y2 = self.y_extent
        # Clockwise from bottom-left: BL, TL, TR, BR
        return {"1": (x1, y1), "2": (x1, y2), "3": (x2, y2), "4": (x2, y1)}

    @property
    def footprint_polygon(self) -> Polygon:
        x1, x2 = self.x_extent
        y1, y2 = self.y_extent
        return Polygon(((x1, y1), (x1, y2), (x2, y2), (x2, y1)))

    @property
    def half_weight(self) -> float:
        # tier=2 doubles cargo count; weight reflects total stack weight
        return (self.cargo.weight * self.tier) / 2.0
