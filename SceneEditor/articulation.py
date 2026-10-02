from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np

from ..assets.discovery import _visual_part_map, parse_parts
from ..contracts import PartSpec


@dataclass
class JointSpec:
    name: str
    joint_type: str
    child_link: str
    axis: np.ndarray
    qpos_index: int = -1
    dof: int = 0
    limits: tuple[float, float] = (-math.inf, math.inf)


@dataclass
class VisualSpec:
    link_name: str
    part_id: int | None
    mesh_path: Path
    origin_xyz: np.ndarray
    origin_wxyz: list[float]
    mesh_scale: np.ndarray


def _quat_from_rpy(values: Iterable[float]) -> list[float]:
    roll, pitch, yaw = [float(value) * 0.5 for value in values]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy]


def _quat_mul(a: Iterable[float], b: Iterable[float]) -> np.ndarray:
    aw, ax, ay, az = [float(value) for value in a]
    bw, bx, by, bz = [float(value) for value in b]
    return np.asarray([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], dtype=float)


def _quat_inv(value: Iterable[float]) -> np.ndarray:
    q = np.asarray(list(value), dtype=float)
    return np.asarray([q[0], -q[1], -q[2], -q[3]], dtype=float) / max(float(np.dot(q, q)), 1e-12)


def _rotate_vector(quaternion: Iterable[float], vector: Iterable[float]) -> np.ndarray:
    q = np.asarray(list(quaternion), dtype=float)
    v = np.asarray([0.0, *list(vector)], dtype=float)
    return _quat_mul(_quat_mul(q, v), _quat_inv(q))[1:]


def _parse_float_list(value: str, size: int, default: Iterable[float]) -> np.ndarray:
    try:
        values = [float(item) for item in value.split()]
        if len(values) == size:
            return np.asarray(values, dtype=np.float64)
    except Exception:
        pass
    return np.asarray(list(default), dtype=np.float64)


def parse_joint_specs(urdf: Path) -> Dict[str, JointSpec]:
    root = ET.parse(urdf).getroot()
    result: Dict[str, JointSpec] = {}
    for joint in root.findall("joint"):
        name = joint.attrib.get("name", "")
        child = joint.find("child")
        if not name or child is None:
            continue
        child_link = child.attrib.get("link", "")
        joint_type = joint.attrib.get("type", "fixed").lower()
        axis_node = joint.find("axis")
        axis = _parse_float_list(axis_node.attrib.get("xyz", "") if axis_node is not None else "", 3, (1.0, 0.0, 0.0))
        limits = joint.find("limit")
        lower = float(limits.attrib.get("lower", "-inf")) if limits is not None else -math.inf
        upper = float(limits.attrib.get("upper", "inf")) if limits is not None else math.inf
        result[child_link] = JointSpec(name, joint_type, child_link, axis, limits=(lower, upper))
    return result


def parse_visual_specs(root: Path, urdf: Path, mobility: Path | None = None) -> List[VisualSpec]:
    tree = ET.parse(urdf)
    visual_map = _visual_part_map(urdf, mobility) if mobility is not None and mobility.is_file() else {}
    values: List[VisualSpec] = []
    for link in tree.getroot().findall("link"):
        link_name = link.attrib.get("name", "")
        for visual in link.findall("visual"):
            mesh = visual.find("./geometry/mesh")
            if mesh is None or not mesh.attrib.get("filename"):
                continue
            path = Path(mesh.attrib["filename"])
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                continue
            match = re.search(r"-(\d+)$", visual.attrib.get("name", ""))
            visual_id = int(match.group(1)) if match else None
            mapped = visual_map.get(visual_id) if visual_id is not None else None
            part_id = int(mapped[0]) if mapped is not None else visual_id
            origin = visual.find("origin")
            xyz = _parse_float_list(origin.attrib.get("xyz", "") if origin is not None else "", 3, (0.0, 0.0, 0.0))
            rpy = _parse_float_list(origin.attrib.get("rpy", "") if origin is not None else "", 3, (0.0, 0.0, 0.0))
            mesh_scale = _parse_float_list(mesh.attrib.get("scale", ""), 3, (1.0, 1.0, 1.0))
            values.append(VisualSpec(link_name, part_id, path, xyz, _quat_from_rpy(rpy), mesh_scale))
    return values


class ArticulationSession:
    def __init__(self, source_dir: str | Path, urdf: str | Path, mobility: str | Path, loader_scale: float = 1.0):
        import sapien

        self.source_dir = Path(source_dir)
        self.urdf = Path(urdf)
        self.part_specs: Dict[int, PartSpec] = parse_parts(self.source_dir, self.urdf, Path(mobility))
        self.visual_specs = parse_visual_specs(self.source_dir, self.urdf, Path(mobility))
        self.joint_specs = parse_joint_specs(self.urdf)
        self.scene = sapien.Scene()
        loader = self.scene.create_urdf_loader()
        loader.fix_root_link = True
        loader.scale = float(loader_scale)
        self.articulation = loader.load(str(self.urdf))
        if self.articulation is None:
            raise RuntimeError(f"failed to load articulation: {self.urdf}")
        self.links = {link.get_name(): link for link in self.articulation.get_links()}
        joints = list(self.articulation.get_joints())
        self.joints_by_child: Dict[str, Any] = {}
        qpos_index = 0
        for joint in joints:
            child = joint.get_child_link()
            child_name = child.get_name() if child is not None else ""
            if child_name:
                self.joints_by_child[child_name] = joint
            spec = self.joint_specs.get(child_name)
            dof = int(joint.get_dof())
            if spec is not None:
                spec.qpos_index = qpos_index
                spec.dof = dof
                limits = np.asarray(joint.get_limits(), dtype=float)
                if limits.shape == (1, 2):
                    spec.limits = (float(limits[0, 0]), float(limits[0, 1]))
            qpos_index += dof
        self.qpos = np.asarray(self.articulation.get_qpos(), dtype=np.float64).reshape(-1)

    def apply_control(
        self,
        part_id: int,
        position: Iterable[float],
        quaternion: Iterable[float],
        mode: str,
        object_translation: Iterable[float] | None = None,
        object_quaternion: Iterable[float] | None = None,
        object_scale: Iterable[float] | None = None,
    ) -> bool:
        part = self.part_specs.get(int(part_id))
        joint_spec = self.joint_specs.get(part.link_name) if part is not None else None
        joint = self.joints_by_child.get(part.link_name) if part is not None else None
        if part is None or joint_spec is None or joint is None or joint_spec.dof != 1 or joint_spec.qpos_index < 0:
            return False
        current = self.part_pose(part_id)
        if current is None:
            return False
        index = joint_spec.qpos_index
        value = float(self.qpos[index])
        global_joint = joint.get_global_pose()
        axis_world = _rotate_vector(global_joint.q, joint_spec.axis)
        axis_world /= max(float(np.linalg.norm(axis_world)), 1e-8)
        target_position = np.asarray(list(position), dtype=float)
        if object_translation is not None and object_quaternion is not None and object_scale is not None:
            local = _rotate_vector(_quat_inv(object_quaternion), target_position - np.asarray(list(object_translation), dtype=float))
            target_position = np.asarray(list(object_translation), dtype=float) + _rotate_vector(object_quaternion, local / np.maximum(np.asarray(list(object_scale), dtype=float), 1e-8))
        if joint_spec.joint_type in {"revolute", "continuous"} and mode == "rotate":
            delta = _quat_mul(quaternion, _quat_inv(current[1]))
            vector = delta[1:]
            angle = 2.0 * math.atan2(float(np.linalg.norm(vector)), max(abs(float(delta[0])), 1e-8))
            if float(np.dot(vector, axis_world)) < 0.0:
                angle = -angle
            value += angle
        elif joint_spec.joint_type == "prismatic" and mode == "translate":
            value += float(np.dot(target_position - np.asarray(current[0], dtype=float), axis_world))
        else:
            return False
        lo, hi = joint_spec.limits
        if math.isfinite(lo):
            value = max(value, lo)
        if math.isfinite(hi):
            value = min(value, hi)
        updated = self.qpos.copy()
        updated[index] = value
        self.set_qpos(updated)
        return True

    def set_object_pose(self, translation: Iterable[float], quaternion: Iterable[float]) -> None:
        import sapien

        self.articulation.set_pose(sapien.Pose(list(translation), list(quaternion)))

    def set_qpos(self, values: Iterable[float]) -> None:
        values = np.asarray(list(values), dtype=np.float64).reshape(-1)
        if values.size != self.qpos.size:
            return
        self.qpos = values
        self.articulation.set_qpos(values.astype(np.float32))

    def part_pose(self, part_id: int) -> tuple[list[float], list[float]] | None:
        part = self.part_specs.get(int(part_id))
        if part is None or part.link_name not in self.links:
            return None
        pose = self.links[part.link_name].get_entity_pose()
        return np.asarray(pose.p, dtype=float).tolist(), np.asarray(pose.q, dtype=float).tolist()

    def link_pose(self, link_name: str) -> tuple[list[float], list[float]] | None:
        link = self.links.get(str(link_name))
        if link is None:
            return None
        pose = link.get_entity_pose()
        return np.asarray(pose.p, dtype=float).tolist(), np.asarray(pose.q, dtype=float).tolist()

    def part_records(self) -> list[dict[str, Any]]:
        records = []
        for part_id, part in sorted(self.part_specs.items()):
            joint = self.joint_specs.get(part.link_name)
            pose = self.part_pose(part_id)
            records.append({"part_id": int(part_id), "part_name": part.name, "link_name": part.link_name, "joint_name": joint.name if joint else "", "joint_type": joint.joint_type if joint else "unsupported", "qpos_index": joint.qpos_index if joint else -1, "limits": list(joint.limits) if joint else [-math.inf, math.inf], "pose_world": {"translation_xyz": pose[0], "quaternion_wxyz": pose[1]} if pose else None})
        return records
