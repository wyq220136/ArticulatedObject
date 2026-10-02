from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DatasetGenerator.config_loader import load_config
from DatasetGenerator.export import export_camera, export_models, write_manifest, write_render_index
from DatasetGenerator.finalization.cleanup import remove_unselected, write_indexes
from DatasetGenerator.layout.io import write_json
from DatasetGenerator.layout.manifest_adapter import make_manifest_plan
from DatasetGenerator.placement.planner import generate_plans
from DatasetGenerator.rendering import render_scene, save_frame


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("DatasetGenerator frame-oriented pipeline")
    parser.add_argument("config", help="parameterized dataset .json/.yml/.yaml")
    parser.add_argument("--manifest", help="SceneEditor manifest.json; overrides procedural scene planning")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _frame_complete(entry: Dict[str, Any], object_count: int, part_count: int) -> bool:
    if not all(entry.get(key) and Path(str(entry[key])).exists() for key in ("rgb", "depth", "annotations", "mask_index")):
        return False
    if len(entry.get("objects", [])) != object_count or len(entry.get("parts", [])) != part_count:
        return False
    for item in entry.get("objects", []):
        if not item.get("mask") or not Path(str(item["mask"])).exists():
            return False
    for item in entry.get("parts", []):
        if not item.get("mask") or not Path(str(item["mask"])).exists():
            return False
        if not item.get("pose_file") or not Path(str(item["pose_file"])).exists():
            return False
        pose = item.get("ob_in_cam")
        if pose is None or len(pose) != 4 or any(len(row) != 4 for row in pose):
            return False
    return True


def _scene_record(plan: Any, scene_root: Path, camera: Dict[str, Any], models: Dict[str, Any], frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"scene": plan.scene, "frame_count": len(frames), "views_per_scene": len(frames), "camera": str(scene_root / "camera" / "intrinsics.json"), "model": str(scene_root / "model"), "model_index": str(scene_root / "model" / "index.json"), "frames": frames, "target_objects": [item.asset.name for item in plan.objects[:plan.target_count]], "camera_intrinsics": camera, "model_records": models.get("records", [])}


def run(cfg: Dict[str, Any], manifest_path: str | None = None) -> Dict[str, Any]:
    root = Path(cfg["output_root"])
    if root.exists() and cfg.get("overwrite", False):
        shutil.rmtree(root)
    for sub in ("json", "multimodal", "visualization"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    plans = [make_manifest_plan(manifest_path, cfg)] if manifest_path else generate_plans(cfg)
    layout_records: List[Dict[str, Any]] = []
    scene_records: List[Dict[str, Any]] = []
    statuses: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for plan, layout in plans:
        layout_path = root / "json" / f"{plan.scene}.json"
        write_json(layout_path, layout)
        layout_records.append({"scene": plan.scene, "json": str(layout_path), "target_objects": [x.asset.name for x in plan.objects[:plan.target_count]], "target_parts": [{"part_id": x.target_part.part_id, "part_name": x.target_part.name, "part_folder": x.target_part.folder} for x in plan.objects[:plan.target_count]]})
    write_json(root / "json" / "candidate_index.json", {"schema": "unique_pose_pair_candidate_index_v1", "count": len(layout_records), "records": layout_records, "rejected_layouts": []})
    for plan, _layout in plans:
        scene_root = root / "multimodal" / plan.scene
        try:
            camera = export_camera(scene_root, cfg)
            models = export_models(scene_root, plan)
            part_count = sum(len(item.asset.parts) for item in plan.objects)
            frames: List[Dict[str, Any]] = []
            for view_index in range(int(cfg["views_per_scene"])):
                frame = render_scene(plan, "inference", view_index % plan.target_count, cfg, view_index=view_index)
                entry = save_frame(frame, scene_root, view_index)
                if not _frame_complete(entry, len(plan.objects), part_count):
                    raise RuntimeError(f"frame_{view_index:03d} is missing required image or annotation output")
                frames.append(entry)
            scene_record = _scene_record(plan, scene_root, camera, models, frames)
            (scene_root / "manifest.json").write_text(json.dumps({"schema": "dataset_generator_scene_manifest_v2", **scene_record}, ensure_ascii=False, indent=2), encoding="utf-8")
            scene_records.append(scene_record)
            statuses.append({"scene": plan.scene, "status": "ok", "frame_count": len(frames)})
        except Exception as exc:
            statuses.append({"scene": plan.scene, "status": "failed", "error": str(exc)})
            rejected.append({"scene": plan.scene, "reason": str(exc)})
            traceback.print_exc()
    write_render_index(root / "multimodal", statuses)
    remove_unselected(root, {item["scene"] for item in scene_records})
    write_indexes(root, scene_records, scene_records, rejected)
    expected_frames = len(plans) * int(cfg["views_per_scene"])
    actual_frames = sum(int(item["frame_count"]) for item in scene_records)
    if len(scene_records) != len(plans) or actual_frames != expected_frames:
        raise RuntimeError(f"generated {len(scene_records)} scenes and {actual_frames} frames; expected {len(plans)} scenes and {expected_frames} frames")
    return write_manifest(root, scene_records, cfg)


def main() -> None:
    args = _args()
    cfg = load_config(args.config)
    cfg["overwrite"] = bool(args.overwrite)
    if args.manifest:
        cfg["pair_count"] = 1
        cfg["targets_per_scene"] = 1
    result = run(cfg, args.manifest)
    print(json.dumps({"output_root": result["output_root"], "scene_count": result["scene_count"], "frame_count": result["frame_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
