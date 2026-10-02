from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import trimesh

from ..contracts import Asset, PartSpec


EXCLUDED_PART_KEYWORDS = ("container", "base", "base_body", "main_body", "body", "frame", "support", "mouth")
_RAW_EXTENT_CACHE: Dict[str, np.ndarray] = {}


def is_exportable_part(name: str) -> bool:
    lowered = str(name).lower().strip()
    return bool(lowered) and not any(keyword in lowered for keyword in EXCLUDED_PART_KEYWORDS)


def _mobility_links(path: Path) -> Dict[int, tuple[str, List[int]]]:
    """Read mobility link ids without flattening duplicate part ids.

    PartNet mobility files can reuse a part id in nested link records. The
    scene-builder contract treats the top-level mobility link id as the
    exported part identity, so a flat ``id -> name`` map is incorrect.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}
    out: Dict[int, tuple[str, List[int]]] = {}
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        name = str(item.get("name") or f"link_{item['id']}").strip()
        ids: List[int] = []
        for part in item.get("parts", []):
            if isinstance(part, dict) and isinstance(part.get("id"), int):
                ids.append(int(part["id"]))
        out[int(item["id"])] = (name, ids)
    return out


def _mesh_info(urdf: Path) -> Dict[str, List[tuple[int, str]]]:
    root = ET.parse(urdf).getroot()
    result: Dict[str, List[tuple[int, str]]] = {}
    for link in root.findall("link"):
        name = link.attrib.get("name", "")
        values: List[tuple[int, str]] = []
        for visual in link.findall("visual"):
            match = re.search(r"-(\d+)$", visual.attrib.get("name", ""))
            mesh = visual.find("./geometry/mesh")
            if match and mesh is not None and mesh.attrib.get("filename"):
                values.append((int(match.group(1)), mesh.attrib["filename"]))
        if values:
            result[name] = values
    return result


def _movable_links(urdf: Path) -> set[str]:
    root = ET.parse(urdf).getroot()
    result: set[str] = set()
    for joint in root.findall("joint"):
        if joint.attrib.get("type", "fixed").lower() == "fixed":
            continue
        child = joint.find("child")
        if child is not None and child.attrib.get("link"):
            result.add(child.attrib["link"])
    return result


def _visual_part_map(urdf: Path, mobility: Path) -> Dict[int, tuple[int, str, str, List[str], List[int]]]:
    """Map visual mesh ids to mobility link ids and link-local mesh paths."""
    mobility_links = _mobility_links(mobility)
    visuals = _mesh_info(urdf)
    result: Dict[int, tuple[int, str, str, List[str], List[int]]] = {}
    for link_id, (name, part_ids) in mobility_links.items():
        wanted = set(part_ids)
        candidates: List[tuple[int, str, List[str], List[int]]] = []
        for link_name, entries in visuals.items():
            matched = [(pid, rel) for pid, rel in entries if pid in wanted]
            if matched:
                paths = list(dict.fromkeys(rel for _pid, rel in matched))
                ids = list(dict.fromkeys(pid for pid, _rel in matched))
                candidates.append((len(matched), link_name, paths, ids))
        if candidates:
            _count, link_name, paths, ids = max(candidates, key=lambda value: value[0])
            for visual_id in ids:
                result[visual_id] = (link_id, name, link_name, paths, ids)
    return result


def _resolve(root: Path, rel: str) -> Optional[Path]:
    if "://" in rel and not rel.lower().startswith("file://"):
        return None
    value = rel[7:] if rel.lower().startswith("file://") else rel
    path = Path(value)
    return path if path.is_absolute() else root / path


def parse_parts(root: Path, urdf: Path, mobility: Path) -> Dict[int, PartSpec]:
    movable = _movable_links(urdf)
    visual_map = _visual_part_map(urdf, mobility)
    parts: Dict[int, PartSpec] = {}
    for _visual_id, (link_id, name, link_name, paths, visual_ids) in visual_map.items():
        if link_name not in movable or not is_exportable_part(name):
            continue
        part = parts.setdefault(link_id, PartSpec(link_id, name, link_name))
        for rel in paths:
            if rel not in part.mesh_paths:
                part.mesh_paths.append(rel)
        for visual_id in visual_ids:
            if visual_id not in part.visual_ids:
                part.visual_ids.append(visual_id)
    return parts


def discover(models_root: Path, limit: int | None = None) -> List[Asset]:
    found: List[Asset] = []
    for category in sorted(models_root.iterdir()) if models_root.exists() else []:
        if not category.is_dir() or category.name.startswith("PartModels"):
            continue
        for instance in sorted(category.iterdir()):
            if not instance.is_dir():
                continue
            urdf, mobility = instance / "mobility.urdf", instance / "mobility_v2.json"
            if not (urdf.exists() and mobility.exists()):
                continue
            parts = parse_parts(instance, urdf, mobility)
            if not parts:
                continue
            found.append(Asset(category.name, instance.name, instance, urdf, _default_scale(category.name), parts))
            if limit and len(found) >= limit:
                return found
    return found


def _default_scale(category: str) -> float:
    return {"kettle": 0.15, "dispenser": 0.14, "bottle": 0.14, "keyboard": 0.135, "box": 0.17, "microwave": 0.18, "oven": 0.18, "storagefurniture": 0.22}.get(category.lower(), 0.16)


def mesh_paths(asset: Asset, part: PartSpec) -> List[Path]:
    return [p for rel in part.mesh_paths if (p := _resolve(asset.root, rel)) is not None and p.exists()]


def _all_mesh_paths(asset: Asset) -> List[Path]:
    """Return every visual mesh referenced by the URDF, including fixed bodies.

    Articulated-part export deliberately filters fixed/base links, but scale
    normalization must describe the complete object so a large base body does
    not make the object unexpectedly oversized or undersized in the frame.
    """
    paths: List[Path] = []
    try:
        for values in _mesh_info(asset.urdf).values():
            for _visual_id, rel in values:
                path = _resolve(asset.root, rel)
                if path is not None and path.exists() and path not in paths:
                    paths.append(path)
    except Exception:
        return []
    return paths


def _mesh_bounds(paths: Iterable[Path]) -> np.ndarray:
    bounds: List[np.ndarray] = []
    for path in paths:
        try:
            mesh = trimesh.load_mesh(path, process=False)
            value = np.asarray(mesh.bounds, dtype=float)
            if value.shape == (2, 3) and np.isfinite(value).all():
                bounds.append(value)
        except Exception:
            continue
    if not bounds:
        return np.stack([np.zeros(3, dtype=float), np.ones(3, dtype=float) * 0.08])
    stacked = np.stack(bounds)
    return np.stack([stacked[:, 0].min(axis=0), stacked[:, 1].max(axis=0)])


def asset_extent(asset: Asset) -> np.ndarray:
    """Return the complete visual extent after the asset loader scale."""
    cache_key = str(asset.root.resolve())
    bounds = _RAW_EXTENT_CACHE.get(cache_key)
    if bounds is None:
        bounds = _mesh_bounds(_all_mesh_paths(asset))
        _RAW_EXTENT_CACHE[cache_key] = bounds
    return np.maximum(bounds[1] - bounds[0], 1e-5) * float(asset.scale)


def normalize_assets(assets: Iterable[Asset], settings: Dict[str, object] | None = None) -> None:
    """Normalize every asset to a common maximum visual dimension in metres."""
    options = settings or {}
    if not bool(options.get("enabled", True)):
        return
    target = float(options.get("target_max_extent", 0.24))
    min_scale = float(options.get("min_scale", 0.02))
    max_scale = float(options.get("max_scale", 1.0))
    if target <= 0.0 or min_scale <= 0.0 or max_scale < min_scale:
        raise ValueError("normalization requires target_max_extent > 0 and valid scale bounds")
    for asset in assets:
        cache_key = str(asset.root.resolve())
        raw_bounds = _RAW_EXTENT_CACHE.get(cache_key)
        if raw_bounds is None:
            raw_bounds = _mesh_bounds(_all_mesh_paths(asset))
            _RAW_EXTENT_CACHE[cache_key] = raw_bounds
        raw_extent = float(np.max(raw_bounds[1] - raw_bounds[0]))
        if not np.isfinite(raw_extent) or raw_extent <= 1e-6:
            continue
        asset.scale = float(np.clip(target / raw_extent, min_scale, max_scale))


def part_extent(asset: Asset, part: PartSpec) -> np.ndarray:
    bounds = _mesh_bounds(mesh_paths(asset, part))
    return np.maximum(bounds[1] - bounds[0], 1e-5) * float(asset.scale)
