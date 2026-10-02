from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .articulation import ArticulationSession, parse_visual_specs
from .pose import relative_pose
from .preview import raw_meshes


@dataclass
class ObjectNodes:
    root: Any
    links: dict[str, Any] = field(default_factory=dict)
    meshes: list[Any] = field(default_factory=list)


class SceneNodeRegistry:
    """Persistent Viser nodes; pose updates never rebuild mesh handles."""

    def __init__(self, server: Any, status: Callable[[str], None] | None = None):
        self.server = server
        self.status = status
        self.nodes: dict[int, ObjectNodes] = {}

    def _report(self, message: str) -> None:
        if self.status is not None:
            self.status(message)

    def _remove_handles(self, handles: list[Any]) -> None:
        for handle in handles:
            try:
                handle.remove()
            except Exception:
                pass

    def remove(self, slot: int) -> None:
        nodes = self.nodes.pop(int(slot), None)
        if nodes is None:
            return
        # Removing a parent recursively removes descendants in Viser. Removing
        # children again emits stale-node warnings and can race with callbacks.
        self._remove_handles([nodes.root])

    def clear(self) -> None:
        for slot in list(self.nodes):
            self.remove(slot)

    def rebuild_object(self, item: Any, session: ArticulationSession | None) -> None:
        self.remove(item.slot)
        self.build_object(item, session)

    def _link_local_pose(self, item: Any, session: ArticulationSession | None, link_name: str) -> tuple[list[float], list[float]]:
        if session is None:
            return [0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]
        pose = session.link_pose(link_name)
        if pose is None:
            return [0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]
        position, quaternion = relative_pose(item.translation_xyz, item.quaternion_wxyz, pose[0], pose[1])
        position = (np.asarray(position, dtype=float) * float(item.scale_xyz[0])).tolist()
        return position, quaternion

    def build_object(self, item: Any, session: ArticulationSession | None) -> None:
        mobility = Path(item.source_dir) / "mobility_v2.json"
        visuals = session.visual_specs if session is not None else parse_visual_specs(Path(item.source_dir), Path(item.urdf), mobility)
        root_name = f"objects/slot_{item.slot:03d}"
        # Apply object scale explicitly to link offsets and mesh handles below.
        # Viser frame scale is not mutable and relying on inherited frame scale
        # causes link meshes to retain their pre-scale size after edits.
        root = self.server.scene.add_frame(root_name, show_axes=False, scale=1.0, wxyz=tuple(item.quaternion_wxyz), position=tuple(item.translation_xyz))
        nodes = ObjectNodes(root=root)
        link_frames: dict[str, Any] = {}
        for visual in visuals:
            if visual.link_name not in link_frames:
                local_position, local_quaternion = self._link_local_pose(item, session, visual.link_name)
                link_frames[visual.link_name] = self.server.scene.add_frame(
                    f"{root_name}/link/{visual.link_name}",
                    show_axes=False,
                    wxyz=tuple(local_quaternion),
                    position=tuple(local_position),
                )
        nodes.links = link_frames
        mesh_index = 0
        for visual in visuals:
            for vertices, faces in raw_meshes(visual.mesh_path):
                scale_value = tuple(float(item.loader_scale * float(item.scale_xyz[0]) * visual.mesh_scale[index]) for index in range(3))
                mesh_name = f"{root_name}/link/{visual.link_name}/mesh_{mesh_index:03d}"
                try:
                    nodes.meshes.append(self.server.scene.add_mesh_simple(
                        mesh_name,
                        vertices=vertices,
                        faces=faces,
                        scale=scale_value,
                        position=tuple(visual.origin_xyz * item.loader_scale * float(item.scale_xyz[0])),
                        wxyz=tuple(visual.origin_wxyz),
                    ))
                except Exception as exc:
                    self._report(f"mesh load failed: {visual.mesh_path.name}: {exc}")
                mesh_index += 1
        self.nodes[item.slot] = nodes

    def update_object(self, item: Any, session: ArticulationSession | None) -> None:
        nodes = self.nodes.get(item.slot)
        if nodes is None:
            self.build_object(item, session)
            return
        nodes.root.position = tuple(item.translation_xyz)
        nodes.root.wxyz = tuple(item.quaternion_wxyz)
        for link_name, frame in nodes.links.items():
            local_position, local_quaternion = self._link_local_pose(item, session, link_name)
            frame.position = tuple(local_position)
            frame.wxyz = tuple(local_quaternion)

    def update_all(self, objects: list[Any], sessions: dict[int, ArticulationSession | None]) -> None:
        expected = {item.slot for item in objects}
        for slot in list(self.nodes):
            if slot not in expected:
                self.remove(slot)
        for item in objects:
            session = sessions.get(item.slot)
            if item.slot not in self.nodes:
                self.build_object(item, session)
            else:
                self.update_object(item, session)
