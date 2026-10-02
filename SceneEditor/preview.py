from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np


def mesh_files(root: str | Path) -> list[Path]:
    return sorted(Path(root).rglob("*.obj"))


def _vertex_bounds(mesh: Any) -> tuple[np.ndarray, np.ndarray] | None:
    if hasattr(mesh, "geometry"):
        bounds = [_vertex_bounds(value) for value in mesh.geometry.values()]
        bounds = [value for value in bounds if value is not None]
        if not bounds:
            return None
        return np.min([value[0] for value in bounds], axis=0), np.max([value[1] for value in bounds], axis=0)
    vertices = getattr(mesh, "vertices", None)
    if vertices is None or len(vertices) == 0:
        return None
    values = np.asarray(vertices, dtype=np.float64)
    return values.min(axis=0), values.max(axis=0)


def mesh_extent(root: str | Path) -> np.ndarray | None:
    try:
        import trimesh
    except ImportError:
        return None
    bounds = []
    for path in mesh_files(root):
        try:
            value = _vertex_bounds(trimesh.load_mesh(path, process=False))
        except Exception:
            continue
        if value is not None:
            bounds.append(value)
    if not bounds:
        return None
    return np.max([value[1] for value in bounds], axis=0) - np.min([value[0] for value in bounds], axis=0)


def preview_scale(root: str | Path, target_max_extent: float = 0.10) -> float:
    extent = mesh_extent(root)
    maximum = float(np.max(extent)) if extent is not None else 0.0
    if maximum <= 1e-8:
        return 1.0
    return float(target_max_extent) / maximum


def scaled_mesh(mesh: Any, scale: float) -> Any:
    """Return vertices/faces for a trimesh mesh or scene at preview scale."""
    if hasattr(mesh, "geometry"):
        geometries = list(mesh.geometry.values())
        return [scaled_mesh(value, scale) for value in geometries]
    vertices = np.asarray(mesh.vertices, dtype=np.float32) * float(scale)
    faces = np.asarray(mesh.faces, dtype=np.uint32)
    return vertices, faces


def scaled_meshes(path: str | Path, scale: float) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    try:
        import trimesh
        mesh = trimesh.load_mesh(path, process=False)
    except Exception:
        return
    values = mesh.geometry.values() if hasattr(mesh, "geometry") else (mesh,)
    for value in values:
        try:
            vertices, faces = scaled_mesh(value, scale)
        except Exception:
            continue
        yield vertices, faces


def raw_meshes(path: str | Path) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    try:
        import trimesh
        mesh = trimesh.load_mesh(path, process=False)
    except Exception:
        return
    values = mesh.geometry.values() if hasattr(mesh, "geometry") else (mesh,)
    for value in values:
        try:
            yield np.asarray(value.vertices, dtype=np.float32), np.asarray(value.faces, dtype=np.uint32)
        except Exception:
            continue
