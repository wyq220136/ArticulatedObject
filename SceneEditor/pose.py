from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def quaternion_from_rpy_deg(values: Iterable[float]) -> list[float]:
    roll, pitch, yaw = [math.radians(float(value)) * 0.5 for value in values]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ]


def rpy_deg_from_quaternion(values: Iterable[float]) -> list[float]:
    w, x, y, z = [float(value) for value in values]
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm <= 1e-8:
        return [0.0, 0.0, 0.0]
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_arg = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_arg)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


def relative_pose(root_position: Iterable[float], root_quaternion: Iterable[float], world_position: Iterable[float], world_quaternion: Iterable[float]) -> tuple[list[float], list[float]]:
    root = np.asarray(list(root_quaternion), dtype=float)
    inverse = np.asarray([root[0], -root[1], -root[2], -root[3]], dtype=float) / max(float(np.dot(root, root)), 1e-12)
    def multiply(a: Iterable[float], b: Iterable[float]) -> np.ndarray:
        aw, ax, ay, az = [float(value) for value in a]
        bw, bx, by, bz = [float(value) for value in b]
        return np.asarray([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], dtype=float)
    delta = np.asarray(list(world_position), dtype=float) - np.asarray(list(root_position), dtype=float)
    local_position = multiply(multiply(inverse, [0.0, *delta.tolist()]), [inverse[0], -inverse[1], -inverse[2], -inverse[3]])[1:]
    local_quaternion = multiply(inverse, world_quaternion)
    return local_position.tolist(), local_quaternion.tolist()


def compose_scaled_pose(root_position: Iterable[float], root_quaternion: Iterable[float], local_position: Iterable[float], local_quaternion: Iterable[float], scale_xyz: Iterable[float]) -> tuple[list[float], list[float]]:
    root = np.asarray(list(root_quaternion), dtype=float)
    vector = np.asarray(list(local_position), dtype=float) * np.asarray(list(scale_xyz), dtype=float)
    def multiply(a: Iterable[float], b: Iterable[float]) -> np.ndarray:
        aw, ax, ay, az = [float(value) for value in a]
        bw, bx, by, bz = [float(value) for value in b]
        return np.asarray([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], dtype=float)
    rotated = multiply(multiply(root, [0.0, *vector.tolist()]), [root[0], -root[1], -root[2], -root[3]])[1:]
    position = np.asarray(list(root_position), dtype=float) + rotated
    return position.tolist(), multiply(root, local_quaternion).tolist()
