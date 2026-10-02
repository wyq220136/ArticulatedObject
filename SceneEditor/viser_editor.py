from __future__ import annotations
import math
import threading
from pathlib import Path
from typing import Any

import numpy as np
from .articulation import ArticulationSession, parse_visual_specs
from .asset_browser import scan_models
from .environment import add_base_scene
from .pose import compose_scaled_pose, quaternion_from_rpy_deg, relative_pose, rpy_deg_from_quaternion
from .preview import raw_meshes
from .scene_state import SceneObject, SceneState, save_manifest
from .scene_nodes import SceneNodeRegistry
def run_app(config: dict[str, Any], platform_name: str = "") -> None:
    try:
        import viser
    except ImportError as exc:
        raise RuntimeError(f"{platform_name} SceneEditor requires viser; install it with: python -m pip install viser") from exc

    server = viser.ViserServer(host=config.get("host", "127.0.0.1"), port=int(config.get("port", 8080)))
    state = SceneState(models_root=config["models_root"], object_max_extent=float(config.get("preview", {}).get("object_max_extent", 0.10)))
    add_base_scene(server, state)
    assets = scan_models(config["models_root"], config.get("models", []))
    sessions: dict[int, ArticulationSession] = {}
    state_lock = threading.RLock()
    nodes = SceneNodeRegistry(server, status=lambda message: setattr(status, "value", message))
    with server.gui.add_folder("Scene"):
        scene_name = server.gui.add_text("scene_name", initial_value=state.name)
        save_button = server.gui.add_button("Save manifest")
        status = server.gui.add_text("status", initial_value=f"assets: {len(assets)}")
    with server.gui.add_folder("Models"):
        selected_asset = server.gui.add_dropdown("asset", options=[item.name for item in assets] or ["(no models)"])
        add_button = server.gui.add_button("Add object")
    with server.gui.add_folder("Objects"):
        selected_slot = server.gui.add_dropdown("selected_slot", options=["(none)"])
        delete_button = server.gui.add_button("Delete selected")
        position = server.gui.add_vector3("position_xyz", initial_value=(0.0, 0.0, 0.05), step=0.01)
        rotation = server.gui.add_vector3("rotation_rpy_deg", initial_value=(0.0, 0.0, 0.0), step=1.0)
        scale = server.gui.add_number("scale", initial_value=1.0, min=0.01, max=10.0, step=0.05, hint="Uniform XYZ scale")
        selected_part = server.gui.add_dropdown("movable_part", options=["(object)"])
        part_info = server.gui.add_text("part_info", initial_value="Select an object to list movable parts")
    translate_gizmo: Any = None
    rotate_gizmo: Any = None
    gizmo_target: tuple[str, SceneObject, ArticulationSession | None, int | None] | None = None

    def item_for_selection() -> SceneObject | None:
        if selected_slot.value == "(none)":
            return None
        return next((item for item in state.objects if item.slot == int(selected_slot.value)), None)

    def load_session(item: SceneObject) -> ArticulationSession | None:
        if item.slot in sessions:
            return sessions[item.slot]
        try:
            session = ArticulationSession(item.source_dir, item.urdf, Path(item.source_dir) / "mobility_v2.json", item.loader_scale)
            session.set_object_pose(item.translation_xyz, item.quaternion_wxyz)
            session.set_qpos(item.qpos or session.qpos)
            sessions[item.slot] = session
            item.qpos = session.qpos.astype(float).tolist()
            item.part_records = session.part_records()
            return session
        except Exception as exc:
            status.value = f"articulation load failed: {exc}"
            return None

    def selected_target() -> tuple[str, SceneObject, ArticulationSession | None, int | None] | None:
        item = item_for_selection()
        if item is None:
            return None
        if selected_part.value == "(object)":
            return "object", item, None, None
        session = load_session(item)
        try:
            part_id = int(str(selected_part.value).split(":", 1)[0])
        except ValueError:
            part_id = None
        return "part", item, session, part_id

    def refresh_scene() -> None:
        with state_lock:
            for item in state.objects:
                session = sessions.get(item.slot)
                if session is not None:
                    session.set_object_pose(item.translation_xyz, item.quaternion_wxyz)
                    session.set_qpos(item.qpos or session.qpos)
                    item.qpos = session.qpos.astype(float).tolist()
                    item.part_records = session.part_records()
            nodes.update_all(state.objects, sessions)
        selected_slot.options = [str(item.slot) for item in state.objects] or ["(none)"]

    def update_part_list(item: SceneObject | None) -> None:
        if item is None:
            selected_part.options = ["(object)"]
            selected_part.value = "(object)"
            part_info.value = "Select an object to list movable parts"
            return
        session = load_session(item)
        records = session.part_records() if session is not None else []
        item.part_records = records
        selected_part.options = ["(object)"] + [f"{r['part_id']}: {r['part_name']}" for r in records]
        selected_part.value = "(object)"
        item.selected_part_id = None
        part_info.value = f"movable parts: {len(records)}"

    def target_pose(target: tuple[str, SceneObject, ArticulationSession | None, int | None]) -> tuple[list[float], list[float]] | None:
        kind, item, session, part_id = target
        if kind == "object":
            return item.translation_xyz, item.quaternion_wxyz
        pose = session.part_pose(int(part_id)) if session is not None and part_id is not None else None
        if pose is None:
            return None
        local = relative_pose(item.translation_xyz, item.quaternion_wxyz, pose[0], pose[1])
        return compose_scaled_pose(item.translation_xyz, item.quaternion_wxyz, local[0], local[1], item.scale_xyz)

    def target_extent(target: tuple[str, SceneObject, ArticulationSession | None, int | None]) -> float:
        kind, item, session, part_id = target
        visuals = session.visual_specs if session is not None else parse_visual_specs(Path(item.source_dir), Path(item.urdf), Path(item.source_dir) / "mobility_v2.json")
        if kind == "part" and part_id is not None:
            visuals = [visual for visual in visuals if visual.part_id == part_id]
        maximum = 0.0
        for visual in visuals:
            for vertices, _faces in raw_meshes(visual.mesh_path):
                extent = np.ptp(vertices, axis=0) * item.loader_scale * np.asarray(item.scale_xyz) * visual.mesh_scale
                maximum = max(maximum, float(np.max(extent)))
        return maximum if maximum > 1e-6 else state.object_max_extent * max(item.scale_xyz)

    def rebuild_gizmos() -> None:
        nonlocal translate_gizmo, rotate_gizmo, gizmo_target
        for handle in (translate_gizmo, rotate_gizmo):
            if handle is not None:
                handle.remove()
        translate_gizmo = rotate_gizmo = None
        target = selected_target()
        if target is None:
            return
        pose = target_pose(target)
        if pose is None:
            return
        extent = target_extent(target)
        size = max(1e-4, extent * 0.8)
        translate_gizmo = server.scene.add_transform_controls("interaction/translate", scale=size, disable_rotations=True, position=tuple(pose[0]), wxyz=tuple(pose[1]), visible=True)
        rotate_gizmo = server.scene.add_transform_controls("interaction/rotate", scale=size, disable_axes=True, disable_sliders=True, position=tuple(pose[0]), wxyz=tuple(pose[1]), visible=True)
        gizmo_target = target

        @translate_gizmo.on_update
        def _translate(event: Any) -> None:
            if event.phase in {"update", "end"}:
                with state_lock:
                    apply_gizmo("translate", translate_gizmo)

        @rotate_gizmo.on_update
        def _rotate(event: Any) -> None:
            if event.phase in {"update", "end"}:
                with state_lock:
                    apply_gizmo("rotate", rotate_gizmo)

    def sync_gizmos() -> None:
        target = selected_target()
        pose = target_pose(target) if target else None
        if pose is None:
            return
        for handle in (translate_gizmo, rotate_gizmo):
            if handle is not None:
                handle.position = tuple(pose[0])
                handle.wxyz = tuple(pose[1])

    def apply_gizmo(mode: str, control: Any) -> None:
        nonlocal gizmo_target
        target = gizmo_target or selected_target()
        if target is None:
            return
        kind, item, session, part_id = target
        if kind == "object":
            item.translation_xyz = [float(value) for value in control.position]
            item.quaternion_wxyz = [float(value) for value in control.wxyz]
            item.yaw_rad = math.radians(rpy_deg_from_quaternion(item.quaternion_wxyz)[2])
            position.value = tuple(item.translation_xyz)
            rotation.value = tuple(rpy_deg_from_quaternion(item.quaternion_wxyz))
            active_session = sessions.get(item.slot)
            if active_session is not None:
                active_session.set_object_pose(item.translation_xyz, item.quaternion_wxyz)
            refresh_scene()
            sync_gizmos()
        elif session is not None and part_id is not None and session.apply_control(part_id, control.position, control.wxyz, mode, item.translation_xyz, item.quaternion_wxyz, item.scale_xyz):
            item.qpos = session.qpos.astype(float).tolist()
            item.part_records = session.part_records()
            refresh_scene()
            sync_gizmos()

    @selected_slot.on_update
    def _select_object(_event: Any) -> None:
        item = item_for_selection()
        update_part_list(item)
        refresh_scene()
        if item is not None:
            position.value = tuple(item.translation_xyz)
            rotation.value = tuple(rpy_deg_from_quaternion(item.quaternion_wxyz))
            scale.value = float(item.scale_xyz[0])
        rebuild_gizmos()

    @selected_part.on_update
    def _select_part(_event: Any) -> None:
        item = item_for_selection()
        if item is not None and selected_part.value != "(object)":
            item.selected_part_id = int(str(selected_part.value).split(":", 1)[0])
            record = next((r for r in item.part_records if r["part_id"] == item.selected_part_id), None)
            part_info.value = f"{record['joint_type']} joint, limits={record['limits']}" if record else "selected part"
        elif item is not None:
            item.selected_part_id = None
            part_info.value = f"movable parts: {len(item.part_records)}"
        refresh_scene()
        rebuild_gizmos()

    @position.on_update
    def _position(_event: Any) -> None:
        item = item_for_selection()
        if item is not None and selected_part.value == "(object)":
            item.translation_xyz = [float(value) for value in position.value]
            refresh_scene(); sync_gizmos()

    @rotation.on_update
    def _rotation(_event: Any) -> None:
        item = item_for_selection()
        if item is not None and selected_part.value == "(object)":
            item.quaternion_wxyz = quaternion_from_rpy_deg(rotation.value)
            item.yaw_rad = math.radians(float(rotation.value[2]))
            refresh_scene(); sync_gizmos()

    @scale.on_update
    def _scale(_event: Any) -> None:
        item = item_for_selection()
        if item is not None:
            uniform_scale = max(0.01, float(scale.value))
            item.scale_xyz = [uniform_scale, uniform_scale, uniform_scale]
            nodes.rebuild_object(item, sessions.get(item.slot))
            refresh_scene(); rebuild_gizmos()

    @add_button.on_click
    def _add(_event: Any) -> None:
        record = next((asset for asset in assets if asset.name == selected_asset.value), None)
        if record is not None:
            item = state.add(record)
            selected_slot.value = str(item.slot)
            update_part_list(item)
            refresh_scene(); rebuild_gizmos()
            status.value = f"objects: {len(state.objects)}"

    @delete_button.on_click
    def _delete(_event: Any) -> None:
        item = item_for_selection()
        if item is not None:
            sessions.pop(item.slot, None)
            state.remove(item.slot)
            update_part_list(None); refresh_scene(); rebuild_gizmos()

    @save_button.on_click
    def _save(_event: Any) -> None:
        state.name = str(scene_name.value).strip() or "scene_000"
        for item in state.objects:
            session = sessions.get(item.slot)
            if session is not None:
                item.qpos = session.qpos.astype(float).tolist()
                item.part_records = session.part_records()
        target = Path(config["manifest_output_dir"]) / f"{state.name}.json"
        save_manifest(state, target)
        status.value = f"saved: {target}"

    refresh_scene()
    print(f"SceneEditor assets={len(assets)} manifest_output_dir={config['manifest_output_dir']}")
    print(f"Viser URL: http://{config.get('host', '127.0.0.1')}:{config.get('port', 8080)}")
    server.sleep_forever()
