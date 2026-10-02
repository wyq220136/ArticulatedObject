from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .preview import preview_scale


@dataclass
class SceneObject:
    slot: int
    object: str
    category: str
    source_dir: str
    urdf: str
    loader_scale: float = 1.0
    translation_xyz: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.04])
    quaternion_wxyz: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    yaw_rad: float = 0.0
    scale_xyz: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    qpos: List[float] = field(default_factory=list)
    selected_part_id: int | None = None
    part_records: List[Dict[str, Any]] = field(default_factory=list)

    def as_manifest(self) -> Dict[str, Any]:
        uniform_scale = max(0.01, float(self.scale_xyz[0]))
        # Keep the value both at object level (easy for generic consumers) and
        # in pose (the canonical SceneEditor manifest location).
        return {"slot": self.slot, "object": self.object, "category": self.category, "source_dir": self.source_dir, "urdf": self.urdf, "loader_scale": self.loader_scale, "scale": uniform_scale, "pose": {"translation_xyz": self.translation_xyz, "quaternion_wxyz": self.quaternion_wxyz, "yaw_rad": self.yaw_rad, "scale": uniform_scale, "scale_xyz": [uniform_scale, uniform_scale, uniform_scale]}, "qpos": self.qpos, "articulation": {"qpos": self.qpos, "selected_part_id": self.selected_part_id, "parts": self.part_records}, "is_target": True}


@dataclass
class SceneState:
    name: str = "scene_000"
    models_root: str = ""
    objects: List[SceneObject] = field(default_factory=list)
    table: Dict[str, Any] = field(default_factory=lambda: {"enabled": True, "center_xy": [0.0, -0.035], "top_z": 0.0, "top_thickness": 0.045, "height": 1.0, "length": 1.0, "depth": 1.0, "top_color": [0.78, 0.70, 0.56, 1.0], "leg_color": [0.30, 0.24, 0.20, 1.0]})
    camera: Dict[str, Any] = field(default_factory=lambda: {"look_at_xyz": [0.0, -0.035, 0.12], "distance": 1.35, "azimuth_deg": 0.0, "elevation_deg": 30.0, "fov_deg": 40.0})
    object_max_extent: float = 0.10

    def add(self, record: Any, slot: int | None = None) -> SceneObject:
        selected = max((item.slot for item in self.objects), default=-1) + 1 if slot is None else int(slot)
        item = SceneObject(selected, record.name, record.category, record.root, record.urdf)
        item.loader_scale = preview_scale(record.root, self.object_max_extent)
        item.translation_xyz[2] = float(self.table.get("top_z", 0.0)) + self.object_max_extent * 0.5
        # Joint limits/qpos are populated lazily by the UI loader. Keeping
        # SceneState independent from SAPIEN makes manifest editing usable in
        # a lightweight Python process as well.
        item.qpos = []
        self.objects.append(item)
        return item

    def remove(self, slot: int) -> None:
        self.objects = [item for item in self.objects if item.slot != int(slot)]

    def as_manifest(self) -> Dict[str, Any]:
        return {"schema": "dataset_generator_scene_manifest_v1", "scene": {"name": self.name, "profile": "interactive_scene"}, "models_root": self.models_root, "table": self.table, "camera": self.camera, "objects": [item.as_manifest() for item in self.objects]}


def save_manifest(state: SceneState, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state.as_manifest(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target
