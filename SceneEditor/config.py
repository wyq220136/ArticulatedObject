from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


DEFAULTS = {
    "models_root": "/path/to/sapien/Models",
    "manifest_output_dir": "./scene_manifests",
    "models": [],
    "preview": {"object_max_extent": 0.10},
    "host": "127.0.0.1",
    "port": 8080,
}


def load_config(path: str | Path) -> Dict[str, Any]:
    source = Path(path).resolve()
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("SceneEditor config requires PyYAML") from exc
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("SceneEditor config must contain a YAML object")
    cfg = {**DEFAULTS, **data}

    def resolve_config_path(value: Any) -> str:
        target = Path(str(value)).expanduser()
        if not target.is_absolute():
            target = source.parent / target
        return str(target.resolve())

    cfg["models_root"] = resolve_config_path(cfg["models_root"])
    cfg["manifest_output_dir"] = resolve_config_path(cfg["manifest_output_dir"])
    if cfg["models"] is None:
        cfg["models"] = []
    if not isinstance(cfg["models"], list):
        raise ValueError("SceneEditor config field 'models' must be a YAML list")
    preview = cfg["preview"]
    if not isinstance(preview, dict):
        raise ValueError("SceneEditor config field 'preview' must be a YAML object")
    preview["object_max_extent"] = float(preview.get("object_max_extent", 0.10))
    if not 0.05 <= preview["object_max_extent"] <= 0.1:
        raise ValueError("preview.object_max_extent must be between 0.05 and 0.1")
    cfg["config_path"] = str(source)
    cfg["port"] = int(cfg["port"])
    return cfg
