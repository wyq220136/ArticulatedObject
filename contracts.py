from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PartSpec:
    part_id: int
    name: str
    link_name: str = ""
    mesh_paths: List[str] = field(default_factory=list)
    visual_ids: List[int] = field(default_factory=list)

    @property
    def folder(self) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in self.name).strip("_") or "part"
        return f"{self.part_id:04d}_{safe}"


@dataclass
class Asset:
    category: str
    instance_id: str
    root: Path
    urdf: Path
    scale: float
    parts: Dict[int, PartSpec] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.category}_{self.instance_id}"


@dataclass
class ObjectPlacement:
    slot: int
    asset: Asset
    xy: Tuple[float, float]
    yaw: float
    is_target: bool
    target_part: Optional[PartSpec] = None
    z: Optional[float] = None
    qpos: Optional[List[float]] = None
    # Uniform scale edited in SceneEditor.  ``asset.scale`` remains the
    # category/model normalization scale and is kept separate deliberately.
    scale: float = 1.0


@dataclass
class ScenePlan:
    scene: str
    profile: str
    objects: List[ObjectPlacement]
    camera: Dict[str, Any]
    table: Dict[str, Any]
    target_count: int


@dataclass
class FrameResult:
    scene: str
    view: str
    rgb: Any
    depth: Any
    object_mask: Any
    target_masks: Dict[str, Any]
    cam_params: Dict[str, Any]
    target_records: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    width: int
    height: int
    fov_deg: float
    pose_annotations: Dict[str, Any] = field(default_factory=dict)
    object_masks: Dict[str, Any] = field(default_factory=dict)
    part_annotations: Dict[str, Any] = field(default_factory=dict)
    camera_pose: Any = None
