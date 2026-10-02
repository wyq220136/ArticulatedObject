from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict

from ..contracts import ScenePlan


def export_camera(scene_root: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    render = cfg["render"]
    scale = float(render.get("render_scale", 1.0))
    width = max(320, int(round(int(render["width"]) * scale)))
    height = max(240, int(round(int(render["height"]) * scale)))
    fov_deg = float(cfg["camera"].get("fov_deg", 40.0))
    fy = height / (2.0 * math.tan(math.radians(fov_deg) / 2.0))
    fx = fy * width / max(1.0, float(height))
    value = {"schema": "dataset_generator_camera_intrinsics_v1", "width": width, "height": height, "fov_deg": fov_deg, "fx": fx, "fy": fy, "cx": (width - 1) / 2.0, "cy": (height - 1) / 2.0, "coordinate_system": "SAPIEN camera x-forward y-left z-up", "depth_unit": "millimetres uint16 on disk"}
    path = scene_root / "camera" / "intrinsics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def _copy_materials(obj_path: Path, out_dir: Path) -> list[str]:
    copied: list[str] = []
    try:
        lines = obj_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        lines = []
    names = [line.split(maxsplit=1)[1].strip() for line in lines if line.lower().startswith("mtllib ") and len(line.split(maxsplit=1)) == 2]
    for name in names:
        source = obj_path.parent / name
        if source.exists():
            target = out_dir / source.name
            shutil.copyfile(source, target)
            copied.append(str(target))
            for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
                fields = line.split(maxsplit=1)
                if len(fields) == 2 and fields[0].lower().startswith("map_"):
                    texture = source.parent / fields[1].strip()
                    if texture.exists():
                        shutil.copyfile(texture, out_dir / texture.name)
                        copied.append(str(out_dir / texture.name))
    return copied


def export_models(scene_root: Path, plan: ScenePlan) -> Dict[str, Any]:
    model_root = scene_root / "model"
    records: list[Dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for item in plan.objects:
        for part in sorted(item.asset.parts.values(), key=lambda value: value.part_id):
            key = (item.asset.name, part.part_id)
            if key in seen:
                continue
            seen.add(key)
            out_dir = model_root / item.asset.name / part.folder
            out_dir.mkdir(parents=True, exist_ok=True)
            copied: list[str] = []
            for source in (item.asset.root / rel for rel in part.mesh_paths):
                if not source.exists():
                    continue
                target = out_dir / source.name
                shutil.copyfile(source, target)
                copied.append(str(target))
                if source.suffix.lower() == ".obj":
                    _copy_materials(source, out_dir)
            records.append({"object": item.asset.name, "part_id": part.part_id, "part_name": part.name, "part_folder": part.folder, "files": copied, "directory": str(out_dir)})
    index = {"schema": "dataset_generator_scene_model_index_v1", "records": records}
    (model_root / "index.json").parent.mkdir(parents=True, exist_ok=True)
    (model_root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index
