from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from ..assets.discovery import _default_scale, parse_parts
from ..contracts import Asset, ObjectPlacement, ScenePlan
from ..placement.planner import _frame_camera, _variants, choose_part
from .schema import layout_json


def load_scene_manifest(path: str | Path) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != "dataset_generator_scene_manifest_v1":
        raise ValueError("unsupported SceneEditor manifest schema")
    if not isinstance(value.get("objects"), list) or not value["objects"]:
        raise ValueError("manifest must contain at least one object")
    return value


def _manifest_uniform_scale(pose: Dict[str, Any], slot: Any, object_scale: Any = None) -> float:
    """Read the canonical uniform scale, including old manifest variants."""
    raw = pose.get("scale")
    if raw is None:
        # Accept manifests written by older SceneEditor builds that stored the
        # uniform value beside ``pose`` rather than inside it.
        raw = object_scale
    if raw is None:
        values = pose.get("scale_xyz", [1.0, 1.0, 1.0])
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"invalid scale for slot {slot}")
        raw = values[0]
    value = float(raw)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"invalid scale for slot {slot}: {raw}")
    return value


def make_manifest_plan(path: str | Path, cfg: Dict[str, Any]) -> Tuple[ScenePlan, Dict[str, Any]]:
    manifest = load_scene_manifest(path)
    models_root = Path(manifest.get("models_root") or cfg["models_root"])
    by_name = {}
    for raw in manifest["objects"]:
        root = Path(raw.get("source_dir") or models_root / str(raw["category"]) / str(raw["object"]).removeprefix(f"{raw['category']}_"))
        urdf = Path(raw.get("urdf") or root / "mobility.urdf")
        if not root.is_dir() or not urdf.is_file():
            raise ValueError(f"object asset path is unavailable: {root}")
        instance = root.name
        category = str(raw["category"])
        mobility = root / "mobility_v2.json"
        parts = parse_parts(root, urdf, mobility)
        by_name[str(raw["object"])] = Asset(category, instance, root, urdf, _default_scale(category), parts)
    objects: List[ObjectPlacement] = []
    json_objects: List[Dict[str, Any]] = []
    for raw in sorted(manifest["objects"], key=lambda value: int(value["slot"])):
        asset = by_name.get(str(raw["object"]))
        if asset is None:
            raise ValueError(f"manifest object not found under models_root: {raw['object']}")
        pose = raw["pose"]
        translation = [float(value) for value in pose["translation_xyz"]]
        quaternion = [float(value) for value in pose["quaternion_wxyz"]]
        yaw = float(pose.get("yaw_rad", 2.0 * math.atan2(quaternion[3], quaternion[0])))
        uniform_scale = _manifest_uniform_scale(pose, raw["slot"], raw.get("scale"))
        if not asset.parts:
            raise ValueError(f"manifest object has no movable exportable parts: {asset.name}")
        target_part = choose_part(asset, list(cfg.get("scene_policy", {}).get("target_part_kinds", [])))
        asset.scale = float(raw.get("loader_scale", asset.scale))
        item = ObjectPlacement(
            int(raw["slot"]), asset, (translation[0], translation[1]), yaw,
            bool(raw.get("is_target", True)), target_part, translation[2],
            [float(value) for value in raw.get("qpos", [])], uniform_scale,
        )
        objects.append(item)
        scale_xyz = [uniform_scale, uniform_scale, uniform_scale]
        json_objects.append({"slot": item.slot, "object": asset.name, "category": asset.category, "source_dir": str(asset.root), "loader_scale": asset.scale, "qpos": list(raw.get("qpos", [])), "pose": {"translation_xyz": translation, "yaw_rad": yaw, "quaternion_wxyz": quaternion, "scale": uniform_scale, "scale_xyz": scale_xyz}, "articulation": raw.get("articulation", {"qpos": list(raw.get("qpos", [])), "parts": []}), "is_target": item.is_target, "target_part": {"part_id": target_part.part_id, "part_name": target_part.name, "part_folder": target_part.folder}, "target_parts": [{"part_id": target_part.part_id, "part_name": target_part.name, "part_folder": target_part.folder}]})
    scene_name = str(manifest.get("scene", {}).get("name", "scene_000"))
    table = dict(manifest.get("table", {}))
    camera = _frame_camera(objects, dict(manifest.get("camera", cfg["camera"])), cfg)
    variants = _variants(scene_name, objects, camera, table, len(objects), cfg)
    policies = [{"slot": item.slot, "target_object": item.asset.name, "target_part": {"part_id": item.target_part.part_id, "part_name": item.target_part.name, "part_folder": item.target_part.folder}, "reference_open_fraction": 0.0, "inference_open_fraction": 0.06} for item in objects]
    layout = layout_json(scene_name, str(manifest.get("scene", {}).get("profile", "interactive_scene")), json_objects, variants, policies, str(models_root), table)
    return ScenePlan(scene_name, "interactive_scene", objects, camera, table, len(objects)), layout
