"""CAD export service and latest-file registry."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .color_mapping import load_color_mapping, resolve_color
from .dxf_writer import write_dxf
from .layout_rules import build_layout_model


@dataclass(frozen=True)
class CadExportResult:
    path: Path
    available: bool


class CadExportService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Path | None = None
        self._default_output_dir = Path(__file__).resolve().parents[3] / "output"

    def export(
        self,
        test_data: dict[str, Any],
        result_dict: dict[str, Any],
        *,
        output_dir: Path,
        color_map_path: Path,
    ) -> CadExportResult:
        layout = build_layout_model(test_data, result_dict)
        mapping = load_color_mapping(color_map_path)
        resolved = {rect.component_no: resolve_color(rect.component_no, mapping) for rect in layout.cargo_rects}
        filename = f"stowage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dxf"
        output_path = output_dir / filename
        write_dxf(layout, output_path, resolved)
        self._set_latest(output_path)
        return CadExportResult(path=output_path, available=True)

    def get_latest_output(self) -> Path | None:
        with self._lock:
            if self._latest and self._latest.exists():
                return self._latest
            dxf_files = sorted(
                self._default_output_dir.glob("stowage_*.dxf"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            self._latest = dxf_files[0] if dxf_files else None
            return self._latest

    def _set_latest(self, path: Path) -> None:
        with self._lock:
            self._latest = path


cad_export_service = CadExportService()
