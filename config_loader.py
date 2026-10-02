from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULTS: Dict[str, Any] = {
    "output_root": "unique_pose_pair_dataset_50",
    "models_root": "D:/research/sapien/Models",
    "seed": 1234,
    "pair_count": 50,
    "targets_per_scene": 2,
    "views_per_scene": 20,
    "candidate_slack": 20,
    "render": {"render_scale": 0.75, "timeout_sec": 150, "width": 1920, "height": 1080},
    "scene_policy": {"min_clutter": 3, "max_clutter": 8, "target_part_kinds": []},
    "camera": {"look_at_xyz": [0.0, -0.035, 0.12], "distance": 1.05, "azimuth_deg": 0.0, "elevation_deg": 30.0, "roll_deg": 0.0, "fov_deg": 40.0, "lock_table_orientation": True, "desired_fill": 0.82, "framing_margin": 1.05},
    "normalization": {"enabled": True, "target_max_extent": 0.14, "min_scale": 0.02, "max_scale": 1.0},
    "quality": {"min_target_pixels": 100, "min_framing_fill": 0.01},
}


def _merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path) -> Dict[str, Any]:
    source = Path(path).resolve()
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML config requires PyYAML in the sapien environment") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("configuration JSON must contain an object")
    cfg = _merge(DEFAULTS, data)
    cfg["_config_path"] = str(source)
    for key in ("pair_count", "targets_per_scene", "views_per_scene", "seed"):
        cfg[key] = int(cfg[key])
    if cfg["pair_count"] < 1 or cfg["targets_per_scene"] < 1 or cfg["views_per_scene"] < 1:
        raise ValueError("pair_count, targets_per_scene and views_per_scene must be positive")
    cfg["output_root"] = str(Path(cfg["output_root"]).resolve())
    cfg["models_root"] = str(Path(cfg["models_root"]).resolve())
    return cfg
