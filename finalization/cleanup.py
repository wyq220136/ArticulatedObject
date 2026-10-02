from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def write_indexes(root: Path, layouts: List[Dict[str, Any]], records: List[Dict[str, Any]], rejected: List[Dict[str, Any]]) -> None:
    json_root = root / "json"
    layout_schema = "dataset_generator_scene_index_v1" if layouts and "frame_count" in layouts[0] else "unique_pose_pair_selected_layout_index_v1"
    frame_schema = "dataset_generator_scene_frame_index_v1" if records and "frame_count" in records[0] else "unique_pose_pair_visualization_index_v1"
    (json_root / "index.json").write_text(json.dumps({"schema": layout_schema, "count": len(layouts), "records": layouts}, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "visualization" / "index.json").write_text(json.dumps({"schema": frame_schema, "count": len(records), "records": records, "rejected": rejected}, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_unselected(root: Path, selected_scenes: set[str]) -> None:
    for path in (root / "json").glob("scene_*.json"):
        if path.stem not in selected_scenes:
            path.unlink(missing_ok=True)
    for path in (root / "multimodal").glob("scene_*"):
        if path.is_dir() and path.name not in selected_scenes:
            shutil.rmtree(path)
