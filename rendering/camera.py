from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def look_at(position: Iterable[float], target: Iterable[float]) -> np.ndarray:
    pos = np.asarray(list(position), dtype=np.float32)
    dst = np.asarray(list(target), dtype=np.float32)
    forward = dst - pos
    forward /= max(float(np.linalg.norm(forward)), 1e-7)
    left = np.cross(np.asarray([0.0, 0.0, 1.0], dtype=np.float32), forward)
    left /= max(float(np.linalg.norm(left)), 1e-7)
    up = np.cross(forward, left)
    up /= max(float(np.linalg.norm(up)), 1e-7)
    matrix = np.eye(4, dtype=np.float32)
    matrix[:3, :3] = np.stack([forward, left, up], axis=1)
    matrix[:3, 3] = pos
    return matrix


def camera_position(camera: dict) -> np.ndarray:
    target = np.asarray(camera.get("look_at_xyz", [0.0, 0.0, 0.12]), dtype=np.float32)
    az = math.radians(float(camera.get("azimuth_deg", 0.0)))
    el = math.radians(float(camera.get("elevation_deg", 30.0)))
    direction = np.asarray([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)], dtype=np.float32)
    return target + direction * float(camera.get("distance", 1.05))
