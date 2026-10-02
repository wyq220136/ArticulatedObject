from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class AssetRecord:
    category: str
    instance: str
    root: str
    urdf: str
    mobility: str

    @property
    def name(self) -> str:
        return f"{self.category}_{self.instance}"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self) | {"name": self.name}


def _model_path(models_root: Path, spec: Any) -> Path:
    if isinstance(spec, str):
        value = spec.strip()
        if not value:
            raise ValueError("SceneEditor model entries cannot be empty")
        path = Path(value).expanduser()
    elif isinstance(spec, Mapping):
        if "path" in spec:
            path = Path(str(spec["path"])).expanduser()
        elif "category" in spec and "instance" in spec:
            path = Path(str(spec["category"])) / str(spec["instance"])
        else:
            raise ValueError(
                "SceneEditor model entries must contain 'path' or both "
                "'category' and 'instance'"
            )
    else:
        raise ValueError("SceneEditor model entries must be strings or mappings")
    return path if path.is_absolute() else models_root / path


def _record_from_path(path: Path) -> AssetRecord:
    if not path.is_dir():
        raise FileNotFoundError(f"configured SceneEditor model directory not found: {path}")
    urdf, mobility = path / "mobility.urdf", path / "mobility_v2.json"
    if not urdf.is_file() or not mobility.is_file():
        raise FileNotFoundError(
            f"configured model is missing mobility.urdf or mobility_v2.json: {path}"
        )
    return AssetRecord(path.parent.name, path.name, str(path), str(urdf), str(mobility))


def scan_models(
    models_root: str | Path,
    model_specs: Iterable[Any] = (),
) -> List[AssetRecord]:
    """Load only explicitly configured model directories.

    ``model_specs`` accepts paths relative to ``models_root`` (for example
    ``bottle/3517``) or mappings with ``category`` and ``instance`` fields.
    An empty list intentionally returns no records; it never scans the full
    models tree.
    """
    root = Path(models_root).expanduser().resolve()
    records: List[AssetRecord] = []
    seen: set[Path] = set()
    for spec in model_specs:
        path = _model_path(root, spec).expanduser().resolve()
        if path in seen:
            continue
        records.append(_record_from_path(path))
        seen.add(path)
    return records


def asset_metadata(record: AssetRecord) -> Dict[str, Any]:
    value = record.as_dict()
    try:
        value["mobility_data"] = json.loads(Path(record.mobility).read_text(encoding="utf-8"))
    except Exception:
        value["mobility_data"] = None
    return value
