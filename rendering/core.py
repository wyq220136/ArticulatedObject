from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import shutil
import json

import numpy as np
from PIL import Image

from ..assets.discovery import parse_parts
from ..contracts import FrameResult, ScenePlan
from .camera import camera_position, look_at
from .scene import configure_lights, setup_table


def _pose_matrix(pose: Any) -> np.ndarray:
    return np.asarray(pose.to_transformation_matrix(), dtype=np.float32)


def _mask_from_segmentation(seg: np.ndarray, link: Any) -> np.ndarray:
    entity_id = int(link.entity.per_scene_id)
    return np.asarray(seg[..., 1] == entity_id, dtype=np.uint8) * 255


def render_scene(plan: ScenePlan, view_type: str, target_index: int, cfg: Dict[str, Any], view_index: int = 0) -> FrameResult:
    import sapien

    render_cfg = cfg["render"]
    width = max(320, int(round(int(render_cfg["width"]) * float(render_cfg.get("render_scale", 1.0)))))
    height = max(240, int(round(int(render_cfg["height"]) * float(render_cfg.get("render_scale", 1.0)))))
    scene = sapien.Scene()
    scene.set_timestep(0.01)
    configure_lights(scene)
    setup_table(scene, sapien, plan.table)
    target_objects = plan.objects if view_type == "inference" else [plan.objects[target_index]]
    loaded: List[tuple[Any, Any]] = []
    object_records: List[Dict[str, Any]] = []
    articulation_states: Dict[int, List[float]] = {}
    for item in target_objects:
        loader = scene.create_urdf_loader()
        loader.fix_root_link = True
        # ``asset.scale`` normalizes the source model.  ``item.scale`` is the
        # user-authored uniform scale from the SceneEditor manifest; both must
        # be applied at URDF load time so mesh geometry and joint offsets stay
        # in the same coordinate system.
        loader.scale = float(item.asset.scale) * float(item.scale)
        art = loader.load(str(item.asset.urdf))
        if art is None:
            raise RuntimeError(f"failed to load {item.asset.urdf}")
        if item.qpos is not None:
            try:
                values = np.asarray(item.qpos, dtype=np.float32).reshape(-1)
                if values.size == np.asarray(art.get_qpos()).size:
                    art.set_qpos(values)
                else:
                    item.qpos = None
            except Exception:
                item.qpos = None
        if item.qpos is None and view_type == "inference":
            try:
                qpos = np.asarray(art.get_qpos(), dtype=np.float32).reshape(-1)
                limits = np.asarray(art.get_qlimits(), dtype=np.float32)
                if qpos.size and limits.shape == (qpos.size, 2):
                    phase = np.sin((int(view_index) + item.slot * 0.37) * 0.73)
                    for q in range(qpos.size):
                        lo, hi = limits[q]
                        if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
                            qpos[q] = lo + (0.5 + 0.25 * phase) * (hi - lo)
                    art.set_qpos(qpos)
                    articulation_states[item.slot] = qpos.astype(float).tolist()
            except Exception:
                pass
        z = float(item.z if item.z is not None else 0.1)
        quat = [float(np.cos(item.yaw / 2.0)), 0.0, 0.0, float(np.sin(item.yaw / 2.0))]
        art.set_pose(sapien.Pose([float(item.xy[0]), float(item.xy[1]), z], quat))
        loaded.append((item, art))
        if item.slot not in articulation_states:
            try:
                articulation_states[item.slot] = np.asarray(art.get_qpos(), dtype=np.float32).reshape(-1).astype(float).tolist()
            except Exception:
                articulation_states[item.slot] = []
        object_records.append({"slot": item.slot, "object": item.asset.name, "category": item.asset.category, "xy": list(item.xy), "z": z, "yaw_rad": item.yaw, "scale": float(item.scale), "scale_xyz": [float(item.scale)] * 3, "loader_scale": float(item.asset.scale), "is_target": item.is_target, "qpos": articulation_states[item.slot]})
    cam_cfg = dict(plan.camera)
    if view_type == "inference":
        # Preserve the table's world-aligned axes: no azimuth or roll sweep.
        # Viewpoint diversity is supplied by elevation and articulated qpos.
        cam_cfg["azimuth_deg"] = 0.0 if bool(cam_cfg.get("lock_table_orientation", True)) else float(cam_cfg.get("azimuth_deg", 0.0))
        cam_cfg["roll_deg"] = 0.0
        cam_cfg["elevation_deg"] = float(cam_cfg.get("elevation_deg", 30.0)) + 6.0 * np.sin(int(view_index) * 0.73)
    cam = scene.add_camera(f"{plan.scene}_{view_type}_{target_index}", width, height, np.deg2rad(float(cam_cfg.get("fov_deg", 40.0))), 0.1, 100.0)
    cam_pose = look_at(camera_position(cam_cfg), cam_cfg.get("look_at_xyz", [0.0, 0.0, 0.12]))
    cam.set_pose(sapien.Pose(cam_pose))
    scene.update_render()
    cam.take_picture()
    rgba = np.asarray(cam.get_picture("Color"))
    rgb = np.clip(rgba[..., :3] * 255.0, 0, 255).astype(np.uint8)
    position = np.asarray(cam.get_picture("Position"))
    depth = np.maximum(-position[..., 2], 0.0).astype(np.float32)
    seg = np.asarray(cam.get_picture("Segmentation"))
    object_masks: Dict[str, Any] = {}
    target_masks: Dict[str, Any] = {}
    cam_params: Dict[str, Any] = {}
    records: List[Dict[str, Any]] = []
    for item, art in loaded:
        object_key = f"slot{item.slot:02d}_{item.asset.name}"
        links = list(art.get_links())
        link_ids = [int(link.entity.per_scene_id) for link in links]
        object_masks[object_key] = np.isin(seg[..., 1], link_ids).astype(np.uint8) * 255
        by_name = {link.get_name(): link for link in links}
        for part in sorted(item.asset.parts.values(), key=lambda value: value.part_id):
            link = by_name.get(part.link_name)
            part_key = f"{object_key}/{part.folder}"
            if link is None:
                mask = np.zeros(seg.shape[:2], dtype=np.uint8)
                pose = None
            else:
                mask = _mask_from_segmentation(seg, link)
                pose = (np.linalg.inv(cam_pose) @ _pose_matrix(link.get_entity_pose())).tolist()
            target_masks[part_key] = mask
            cam_params[part_key] = pose
            records.append({"object": item.asset.name, "object_key": object_key, "slot": item.slot, "part_id": part.part_id, "part_name": part.name, "part_folder": part.folder, "part_key": part_key, "link_name": part.link_name, "mask_pixels": int(np.count_nonzero(mask)), "mesh_paths": [str(item.asset.root / rel) for rel in part.mesh_paths]})
    object_mask = np.zeros(seg.shape[:2], dtype=np.uint8)
    for mask in object_masks.values():
        object_mask = np.maximum(object_mask, mask)
    name = f"{plan.scene}_view_{target_index:02d}_reference" if view_type == "reference" else f"{plan.scene}_view_{int(view_index):03d}_inference"
    pose_annotations = {r["part_key"]: {"ob_in_cam": cam_params[r["part_key"]], "qpos": articulation_states.get(int(r["slot"]), []), "view_type": view_type, "view_index": int(view_index), "scene": plan.scene} for r in records}
    return FrameResult(name, view_type, rgb, depth, object_mask, target_masks, cam_params, records, object_records, width, height, float(cam_cfg.get("fov_deg", 40.0)), pose_annotations, object_masks, {}, cam_pose.tolist())


def _bbox(mask: np.ndarray) -> List[int] | None:
    ys, xs = np.where(mask > 0)
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)] if len(xs) else None


def save_frame(frame: FrameResult, scene_root: Path, frame_index: int) -> Dict[str, Any]:
    out = scene_root / "frames" / f"frame_{int(frame_index):03d}"
    object_root, part_root, pose_root = out / "object_masks", out / "part_masks", out / "pose"
    for path in (out, object_root, part_root, pose_root):
        path.mkdir(parents=True, exist_ok=True)
    rgb_path, depth_path = out / "rgb.png", out / "depth.png"
    Image.fromarray(frame.rgb).save(rgb_path)
    Image.fromarray(np.clip(frame.depth * 1000.0, 0, 65535).astype(np.uint16)).save(depth_path)
    objects: List[Dict[str, Any]] = []
    object_by_key = {f"slot{int(item['slot']):02d}_{item['object']}": item for item in frame.objects}
    for object_key, mask in frame.object_masks.items():
        path = object_root / f"{object_key}.png"
        Image.fromarray(mask).save(path)
        item = object_by_key.get(object_key, {})
        objects.append({"object_key": object_key, "object": item.get("object"), "slot": item.get("slot"), "mask": str(path), "bbox_xyxy": _bbox(mask), "qpos": item.get("qpos", []), "parts": []})
    object_annotations = {item["object_key"]: item for item in objects}
    parts: List[Dict[str, Any]] = []
    for record in frame.target_records:
        object_key, part_folder = record["part_key"].split("/", 1)
        mask = frame.target_masks[record["part_key"]]
        mask_dir = part_root / object_key
        pose_dir = pose_root / object_key
        mask_dir.mkdir(parents=True, exist_ok=True)
        pose_dir.mkdir(parents=True, exist_ok=True)
        mask_path = mask_dir / f"{part_folder}.png"
        pose_path = pose_dir / f"{part_folder}.json"
        Image.fromarray(mask).save(mask_path)
        annotation = {**record, **frame.pose_annotations.get(record["part_key"], {}), "mask": str(mask_path), "bbox_xyxy": _bbox(mask), "visible": bool(np.count_nonzero(mask))}
        pose_path.write_text(json.dumps(annotation, ensure_ascii=False, indent=2), encoding="utf-8")
        annotation["pose_file"] = str(pose_path)
        parts.append(annotation)
        if object_key in object_annotations:
            object_annotations[object_key]["parts"].append(annotation)
    annotation_path = out / "annotations.json"
    annotation_data = {"schema": "dataset_generator_frame_annotation_v1", "frame_index": int(frame_index), "view_name": frame.scene, "camera_pose_world": frame.camera_pose, "width": frame.width, "height": frame.height, "fov_deg": frame.fov_deg, "rgb": str(rgb_path), "depth": str(depth_path), "objects": objects, "parts": parts}
    annotation_path.write_text(json.dumps(annotation_data, ensure_ascii=False, indent=2), encoding="utf-8")
    mask_index = {"schema": "dataset_generator_mask_index_v1", "objects": {item["object_key"]: item["mask"] for item in objects}, "parts": {item["part_key"]: item["mask"] for item in parts}}
    mask_index_path = out / "mask_index.json"
    mask_index_path.write_text(json.dumps(mask_index, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"frame_index": int(frame_index), "view_name": frame.scene, "rgb": str(rgb_path), "depth": str(depth_path), "annotations": str(annotation_path), "mask_index": str(mask_index_path), "objects": objects, "parts": parts}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
