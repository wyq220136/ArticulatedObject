from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def validate_manifest(value: Dict[str, Any]) -> None:
    if value.get("schema") != "dataset_generator_scene_manifest_v1":
        raise ValueError("unsupported manifest schema")
    if not isinstance(value.get("objects"), list):
        raise ValueError("manifest.objects must be a list")
    slots = []
    for item in value["objects"]:
        for key in ("slot", "object", "category", "source_dir", "urdf", "loader_scale", "pose", "qpos"):
            if key not in item:
                raise ValueError(f"object missing {key}")
        pose = item["pose"]
        if len(pose.get("translation_xyz", [])) != 3 or len(pose.get("quaternion_wxyz", [])) != 4:
            raise ValueError(f"invalid pose for slot {item['slot']}")
        if "scale_xyz" in pose and len(pose["scale_xyz"]) != 3:
            raise ValueError(f"invalid scale_xyz for slot {item['slot']}")
        if "scale_xyz" in pose and any(float(value) <= 0 for value in pose["scale_xyz"]):
            raise ValueError(f"invalid scale_xyz for slot {item['slot']}")
        if "scale" in pose and float(pose["scale"]) <= 0:
            raise ValueError(f"invalid scale for slot {item['slot']}")
        if "scale" in item and float(item["scale"]) <= 0:
            raise ValueError(f"invalid scale for slot {item['slot']}")
        articulation = item.get("articulation", {})
        if articulation:
            if len(articulation.get("qpos", item.get("qpos", []))) != len(item.get("qpos", [])):
                raise ValueError(f"articulation qpos mismatch for slot {item['slot']}")
            if not isinstance(articulation.get("parts", []), list):
                raise ValueError(f"invalid articulation parts for slot {item['slot']}")
        if item["slot"] in slots:
            raise ValueError(f"duplicate slot {item['slot']}")
        slots.append(item["slot"])


def load_manifest(path: str | Path) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must contain an object")
    validate_manifest(value)
    return value
