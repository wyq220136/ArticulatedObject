from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from ..assets.discovery import asset_extent, discover, normalize_assets, part_extent
from ..contracts import Asset, ObjectPlacement, PartSpec, ScenePlan
from ..layout.schema import layout_json
from .collision import repair_positions


def choose_part(asset: Asset, kinds: List[str]) -> PartSpec:
    parts = list(asset.parts.values())
    if kinds:
        parts = [p for p in parts if any(k in p.name.lower() for k in kinds)]
    banned = ("container", "base", "body", "frame", "support", "mouth")
    parts = [p for p in parts if not any(k in p.name.lower() for k in banned)]
    if not parts:
        raise ValueError(f"no target part for {asset.name}")
    priority = ("handle", "button", "lever", "slider", "knob", "door", "drawer", "lid", "wheel")
    parts.sort(key=lambda p: (next((priority.index(k) for k in priority if k in p.name.lower()), 99), p.part_id))
    return parts[0]


def _object_json(item: ObjectPlacement, extent: np.ndarray, target: bool) -> Dict[str, Any]:
    uniform_scale = float(item.scale)
    value: Dict[str, Any] = {"slot": item.slot, "object": item.asset.name, "category": item.asset.category, "source_dir": str(item.asset.root), "loader_scale": item.asset.scale, "scaled_extent": extent.tolist(), "pose": {"translation_xyz": [item.xy[0], item.xy[1], float(item.z or extent[2] * 0.5)], "yaw_rad": item.yaw, "yaw_deg": math.degrees(item.yaw), "quaternion_wxyz": [math.cos(item.yaw * 0.5), 0.0, 0.0, math.sin(item.yaw * 0.5)], "scale": uniform_scale, "scale_xyz": [uniform_scale] * 3}, "placement": {"role": "tabletop_object", "support": "procedural_table", "support_surface_z": 0.0}, "is_target": target}
    if target and item.target_part:
        p = {"part_id": item.target_part.part_id, "part_name": item.target_part.name, "part_folder": item.target_part.folder}
        value.update({"target_folder_slot": item.slot, "target_part": p, "target_parts": [p]})
    return value


def make_scene(index: int, assets: List[Asset], cfg: Dict[str, Any]) -> Tuple[ScenePlan, Dict[str, Any]]:
    rng = np.random.default_rng(int(cfg["seed"]) + index)
    target_count = int(cfg["targets_per_scene"])
    if len(assets) < target_count:
        raise RuntimeError("not enough assets for scene")
    chosen = [assets[(index * target_count + j) % len(assets)] for j in range(target_count)]
    kinds = list(cfg.get("scene_policy", {}).get("target_part_kinds", []))
    parts = [choose_part(a, kinds) for a in chosen]
    # Placement and framing use the complete visual body, not only the target
    # link. This keeps collision bounds, support height, and camera framing in
    # the same coordinate system.
    extents = [asset_extent(a) for a in chosen]
    clutter_count = int(rng.integers(int(cfg["scene_policy"]["min_clutter"]), int(cfg["scene_policy"]["max_clutter"]) + 1))
    clutter_pool = [a for a in assets if a not in chosen]
    clutter = clutter_pool[:clutter_count]
    clutter_extents = [asset_extent(a) for a in clutter]
    positions = repair_positions(extents + clutter_extents, int(cfg["seed"]) + index, (-0.48, 0.48, -0.29, 0.29))
    objects: List[ObjectPlacement] = []
    json_objects: List[Dict[str, Any]] = []
    for slot, (asset, part, extent, xy) in enumerate(zip(chosen, parts, extents, positions)):
        item = ObjectPlacement(slot, asset, xy, float(rng.uniform(-math.pi, math.pi)), True, part, float(extent[2] * 0.5))
        objects.append(item)
        json_objects.append(_object_json(item, extent, True))
    if clutter_extents:
        clutter_pos = positions[target_count:]
        for slot, (asset, extent, xy) in enumerate(zip(clutter, clutter_extents, clutter_pos), target_count):
            item = ObjectPlacement(slot, asset, xy, float(rng.uniform(-math.pi, math.pi)), False, None, float(extent[2] * 0.5))
            objects.append(item)
            json_objects.append(_object_json(item, extent, False))
    cam = _frame_camera(objects, dict(cfg["camera"]), cfg)
    table = {"enabled": True, "center_xy": [0.0, -0.035], "top_z": 0.0, "length": 1.3, "depth": 0.82, "top_thickness": 0.045, "height": 0.72, "top_color": [0.78, 0.7, 0.56, 1.0], "leg_color": [0.3, 0.24, 0.2, 1.0]}
    variants = _variants(f"scene_{index:03d}", objects, cam, table, target_count, cfg)
    policies = [{"slot": i, "target_object": item.asset.name, "target_part": {"part_id": item.target_part.part_id, "part_name": item.target_part.name, "part_folder": item.target_part.folder}, "reference_open_fraction": 0.0, "inference_open_fraction": 0.06} for i, item in enumerate(objects[:target_count])]
    layout = layout_json(f"scene_{index:03d}", "kitchen_counter", json_objects, variants, policies, cfg["models_root"], table)
    return ScenePlan(f"scene_{index:03d}", "kitchen_counter", objects, cam, table, target_count), layout


def _variants(scene_name: str, objects: List[ObjectPlacement], cam: Dict[str, Any], table: Dict[str, Any], count: int, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for target in range(count):
        visible = [objects[target]]
        out.append({"name": f"{scene_name}_view_{target:02d}_reference", "objects": [{"slot": x.slot, "object": x.asset.name, "category": x.asset.category, "source_dir": str(x.asset.root), "loader_scale": x.asset.scale, "pose": {"translation_xyz": [x.xy[0], x.xy[1], float(x.z or 0.0)], "yaw_rad": x.yaw, "scale": float(x.scale), "scale_xyz": [float(x.scale)] * 3}, "is_target": x.is_target} for x in visible], "camera": cam, "look_at_xyz": cam["look_at_xyz"], "distance": cam["distance"], "azimuth_deg": cam["azimuth_deg"], "elevation_deg": cam["elevation_deg"], "fov_deg": cam["fov_deg"], "forced_targets": [{"slot": objects[target].slot, "part_id": objects[target].target_part.part_id}], "view_type": "reference", "target_index": target, "view_index": 0, "width": cfg["render"]["width"], "height": cfg["render"]["height"]})
    for view_index in range(int(cfg.get("views_per_scene", 20))):
        target = view_index % count
        visible = objects
        view_cam = dict(cam)
        # Keep the tabletop axes stable in the image. Diversity comes from a
        # bounded elevation sweep and articulation state, never camera roll or
        # azimuth rotation.
        view_cam["azimuth_deg"] = float(cam.get("azimuth_deg", 0.0))
        view_cam["roll_deg"] = 0.0
        view_cam["elevation_deg"] = float(cam.get("elevation_deg", 30.0)) + 6.0 * math.sin(view_index * 0.73)
        out.append({"name": f"{scene_name}_view_{view_index:03d}_inference", "objects": [{"slot": x.slot, "object": x.asset.name, "category": x.asset.category, "source_dir": str(x.asset.root), "loader_scale": x.asset.scale, "pose": {"translation_xyz": [x.xy[0], x.xy[1], float(x.z or 0.0)], "yaw_rad": x.yaw, "scale": float(x.scale), "scale_xyz": [float(x.scale)] * 3}, "is_target": x.is_target} for x in visible], "camera": view_cam, "look_at_xyz": view_cam["look_at_xyz"], "distance": view_cam["distance"], "azimuth_deg": view_cam["azimuth_deg"], "elevation_deg": view_cam["elevation_deg"], "fov_deg": view_cam["fov_deg"], "forced_targets": [{"slot": objects[target].slot, "part_id": objects[target].target_part.part_id}], "view_type": "inference", "target_index": target, "view_index": view_index, "articulation_state_index": view_index, "width": cfg["render"]["width"], "height": cfg["render"]["height"]})
    return out


def generate_plans(cfg: Dict[str, Any]) -> List[Tuple[ScenePlan, Dict[str, Any]]]:
    assets = discover(Path(cfg["models_root"]), limit=max(32, cfg["pair_count"] * cfg["targets_per_scene"] + 8))
    normalize_assets(assets, cfg.get("normalization", {}))
    kinds = list(cfg.get("scene_policy", {}).get("target_part_kinds", []))
    usable = []
    for asset in assets:
        try:
            choose_part(asset, kinds)
            usable.append(asset)
        except ValueError:
            continue
    required = int(cfg["pair_count"]) * int(cfg["targets_per_scene"])
    if len(usable) < required:
        raise RuntimeError(f"only {len(usable)} usable target assets found under {cfg['models_root']}; need {required}")
    return [make_scene(i, usable, cfg) for i in range(int(cfg["pair_count"]))]


def _frame_camera(objects: List[ObjectPlacement], camera: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Frame the shared scene bounds with a zero-roll, table-aligned camera."""
    if not objects:
        return camera
    bounds = []
    for item in objects:
        extent = asset_extent(item.asset) * float(item.scale)
        radius_xy = 0.5 * float(np.linalg.norm(extent[:2]))
        z_center = float(item.z if item.z is not None else extent[2] * 0.5)
        bounds.append((item.xy[0] - radius_xy, item.xy[0] + radius_xy, item.xy[1] - radius_xy, item.xy[1] + radius_xy, z_center - extent[2] * 0.5, z_center + extent[2] * 0.5))
    xmin = min(value[0] for value in bounds)
    xmax = max(value[1] for value in bounds)
    ymin = min(value[2] for value in bounds)
    ymax = max(value[3] for value in bounds)
    zmin = min(value[4] for value in bounds)
    zmax = max(value[5] for value in bounds)
    center = np.asarray([(xmin + xmax) * 0.5, (ymin + ymax) * 0.5, max(0.06, (zmin + zmax) * 0.5)], dtype=float)
    width = max(320.0, float(cfg["render"]["width"]) * float(cfg["render"].get("render_scale", 1.0)))
    height = max(240.0, float(cfg["render"]["height"]) * float(cfg["render"].get("render_scale", 1.0)))
    vertical_fov = math.radians(float(camera.get("fov_deg", 40.0)))
    horizontal_fov = 2.0 * math.atan(math.tan(vertical_fov * 0.5) * width / height)
    fill = float(camera.get("desired_fill", 0.68))
    margin = float(camera.get("framing_margin", 1.10))
    fill = min(max(fill, 0.35), 0.90)
    xy_radius = max((xmax - xmin) * 0.5, (ymax - ymin) * 0.5, 0.03)
    z_radius = max((zmax - zmin) * 0.5, 0.03)
    horizontal_distance = xy_radius / (math.tan(horizontal_fov * 0.5) * fill)
    vertical_distance = z_radius / (math.tan(vertical_fov * 0.5) * fill)
    camera.update({"look_at_xyz": center.tolist(), "distance": max(0.45, margin * max(horizontal_distance, vertical_distance)), "azimuth_deg": 0.0, "roll_deg": 0.0})
    return camera
