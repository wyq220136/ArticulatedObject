from __future__ import annotations

from typing import Any, Dict


SCHEMA = "unique_pose_pair_cleanref_clutterinf_layout_v2"


def object_json(item: Dict[str, Any], slot: int, target: bool, part: Dict[str, Any] | None = None) -> Dict[str, Any]:
    value = dict(item)
    value["slot"] = int(slot)
    value["is_target"] = bool(target)
    if part is not None:
        value["target_folder_slot"] = int(slot)
        value["target_part"] = dict(part)
        value["target_parts"] = [dict(part)]
    return value


def layout_json(scene: str, profile: str, objects: list[Dict[str, Any]], camera_variants: list[Dict[str, Any]], target_policies: list[Dict[str, Any]], models_root: str, table: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "planned_multi_target_pair",
        "models_root": models_root,
        "scene": {"name": scene, "profile": profile, "semantic_rule": "reference variants contain one clean target object; inference variants contain the same target set plus non-overlapping clutter", "table_altitude": 0.0, "support_surface_z": 0.0, "width": int(camera_variants[0].get("width", 1920)), "height": int(camera_variants[0].get("height", 1080)), "fov_deg": float(camera_variants[0].get("fov_deg", 40.0)), "fixed_camera": True, "camera": camera_variants[0].get("camera", {}), "background_style": "cool_gray_studio", "background": "cool gray sky and pale tabletop with contact shadows", "procedural_table": table, "target_count": len(target_policies)},
        "objects": objects,
        "camera_variants": camera_variants,
        "target_policy": target_policies[0],
        "target_policies": target_policies,
        "target_policies_reference": target_policies,
        "target_policies_inference": target_policies,
    }
