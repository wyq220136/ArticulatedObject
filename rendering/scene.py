from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def add_box(scene: Any, sapien: Any, name: str, center: Tuple[float, float, float], half: Tuple[float, float, float], color: list[float]) -> None:
    builder = scene.create_actor_builder()
    material = sapien.render.RenderMaterial()
    material.base_color = np.asarray(color, dtype=np.float32)
    material.roughness = 0.8
    builder.add_box_visual(pose=sapien.Pose(list(center)), half_size=list(half), material=material)
    builder.add_box_collision(pose=sapien.Pose(list(center)), half_size=list(half))
    builder.build_static(name=name)


def setup_table(scene: Any, sapien: Any, table: Dict[str, Any]) -> None:
    if not bool(table.get("enabled", True)):
        return
    cx, cy = table.get("center_xy", [0.0, -0.035])[:2]
    top_z = float(table.get("top_z", 0.0))
    thickness = float(table.get("top_thickness", 0.045))
    length, depth = float(table.get("length", 1.3)), float(table.get("depth", 0.82))
    add_box(scene, sapien, "procedural_table_top", (cx, cy, top_z - thickness / 2), (length / 2, depth / 2, thickness / 2), table.get("top_color", [0.78, 0.70, 0.56, 1.0]))


def configure_lights(scene: Any) -> None:
    scene.set_ambient_light([0.55, 0.55, 0.55])
    scene.add_directional_light([0.3, 0.8, -1.0], [0.8, 0.8, 0.8], shadow=True)
    scene.add_point_light([1.0, -1.0, 2.0], [0.8, 0.8, 0.8])
    scene.add_point_light([-1.0, 1.0, 1.5], [0.5, 0.6, 0.7])
