"""Load test_data.json into typed domain objects."""
from __future__ import annotations

import json
from pathlib import Path

from .data_models import (
    BypassBoard,
    Cargo,
    FeasibleRange,
    HatchCover,
    Polygon,
    ProblemData,
    VesselStructure,
)


def _polygon_from_dict(d: dict) -> Polygon:
    """Read 4-or-more-corner dict {"1":{x,y,z}, "2":..., ...} -> Polygon."""
    indices = sorted((k for k in d.keys() if k.isdigit()), key=int)
    pts = tuple((float(d[k]["x"]), float(d[k]["y"])) for k in indices)
    return Polygon(pts)


def _load_cargoes(raw: dict) -> dict[str, tuple[Cargo, ...]]:
    out: dict[str, tuple[Cargo, ...]] = {}
    for cargo_type, items in raw.items():
        cargoes = []
        for it in items:
            cargoes.append(Cargo(
                cargo_type=cargo_type,
                cargo_name=it["cargoName"],
                component_no=int(it["componentNo"]),
                cargo_label=it["cargoLabel"],
                length=int(it["length"]),
                width=int(it["width"]),
                height=int(it["height"]),
                weight=float(it["weight"]),
            ))
        out[cargo_type] = tuple(sorted(cargoes, key=lambda c: c.component_no))
    return out


def _load_bypass_boards(raw: list[dict]) -> tuple[BypassBoard, ...]:
    boards: list[BypassBoard] = []
    for b in raw:
        boards.append(BypassBoard(
            layer=int(b["layer"]),
            hatchno=int(b["hatchno"]),
            label=int(b["label"]),
            polygon=_polygon_from_dict(b),
        ))
    return tuple(boards)


def _load_hatch_covers(raw: list[dict]) -> tuple[HatchCover, ...]:
    return tuple(HatchCover(label=int(c["label"]), polygon=_polygon_from_dict(c))
                 for c in raw)


def _load_feasible_ranges(raw: dict) -> tuple[FeasibleRange, ...]:
    out: list[FeasibleRange] = []
    for layer_key, layer_val in raw.items():
        layer_num = int(layer_key.replace("Layer", ""))
        if layer_num == 4:
            poly = _polygon_from_dict(layer_val)
            out.append(FeasibleRange(layer=4, hatch_id=None, polygon=poly))
            continue

        height_dict = layer_val.get("Height", {})
        for k, v in layer_val.items():
            if not k.startswith("Hatch"):
                continue
            poly = _polygon_from_dict(v)
            limit = None
            segments = None
            if k in height_dict:
                hv = height_dict[k]
                if isinstance(hv, list):
                    segments = tuple(hv)
                else:
                    limit = float(hv)
            out.append(FeasibleRange(
                layer=layer_num, hatch_id=k, polygon=poly,
                height_limit=limit, height_segments=segments,
            ))
    return tuple(out)


def load_problem(json_path: str | Path) -> ProblemData:
    """Top-level: parse the JSON spec file into a ProblemData object."""
    text = Path(json_path).read_text(encoding="utf-8")
    return load_problem_from_dict(json.loads(text))


def load_problem_from_dict(raw: dict) -> ProblemData:
    """Build ProblemData from an already-parsed dict (used by HTTP API)."""
    cargoes = _load_cargoes(raw["cargoData"])
    vs_raw = raw["vesselStructure"]
    vessel = VesselStructure(
        bypass_boards=_load_bypass_boards(vs_raw["bypassBoardPosition"]),
        hatch_covers=_load_hatch_covers(vs_raw["hatchCoverPosition"]),
        feasible_ranges=_load_feasible_ranges(vs_raw["stowageFeasibleRange"]),
    )
    return ProblemData(cargoes_by_type=cargoes, vessel=vessel)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parents[2] / "data" / "test_data.json"
    pd = load_problem(p)
    print(f"Cargo types: {list(pd.cargoes_by_type.keys())}")
    for ct, cs in pd.cargoes_by_type.items():
        print(f"  {ct}: {len(cs)} components")
    print(f"Bypass boards: {len(pd.vessel.bypass_boards)}")
    print(f"Hatch covers : {len(pd.vessel.hatch_covers)}")
    print(f"Feasible rngs: {len(pd.vessel.feasible_ranges)}")
    for fr in pd.vessel.feasible_ranges:
        print(f"  Layer{fr.layer} {fr.hatch_id}: bbox={fr.polygon.bbox} "
              f"limit={fr.height_limit} seg={'yes' if fr.height_segments else 'no'}")
