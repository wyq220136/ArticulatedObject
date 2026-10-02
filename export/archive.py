from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def write_manifest(root: Path, records: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    scenes = {x.get("scene", "") for x in records}
    frame_count = sum(int(x.get("frame_count", 0)) for x in records)
    manifest = {"schema": "unique_pose_pair_cleanref_clutterinf_archive_v1", "created": datetime.now().isoformat(timespec="seconds"), "output_root": str(root), "pair_count": frame_count, "scene_count": len(scenes), "frame_count": frame_count, "views_per_scene": int(cfg.get("views_per_scene", 20)), "json_dir": str(root / "json"), "multimodal_dir": str(root / "multimodal"), "visualization_dir": str(root / "visualization"), "policies": {"frame_unit": "each scene contains one frame directory per viewpoint/articulation state", "reference": "scene target objects are represented in every frame", "inference": "same target set plus non-overlapping clutter", "target_uniqueness": "unique object instances and object/part pairs at scene level", "views": "each scene has configurable viewpoint/articulation states", "scale": "fixed source-category loader scale", "axis": "SAPIEN x-forward/y-left/z-up"}, "records": records}
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def write_render_index(root: Path, statuses: List[Dict[str, Any]]) -> None:
    (root / "render_batch_index.json").write_text(json.dumps({"records": statuses}, ensure_ascii=False, indent=2), encoding="utf-8")
