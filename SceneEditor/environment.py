from __future__ import annotations

from typing import Any, Iterable


def _rgb(value: Iterable[float], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    values = list(value)
    if len(values) < 3:
        return fallback
    if max(abs(float(item)) for item in values[:3]) <= 1.0:
        return tuple(max(0, min(255, round(float(item) * 255))) for item in values[:3])
    return tuple(max(0, min(255, round(float(item)))) for item in values[:3])


def _add_box(server: Any, name: str, dimensions: tuple[float, float, float], position: tuple[float, float, float], color: tuple[int, int, int]) -> None:
    server.scene.add_box(name, dimensions=dimensions, position=position, color=color)


def add_base_scene(server: Any, state: Any) -> None:
    """Add the fixed tabletop shared by both UI platforms."""
    table = dict(state.table)
    if bool(table.get("enabled", True)):
        cx, cy = [float(value) for value in table.get("center_xy", [0.0, -0.035])[:2]]
        top_z = float(table.get("top_z", 0.0))
        thickness = float(table.get("top_thickness", 0.045))
        length = float(table.get("length", 1.0))
        depth = float(table.get("depth", 1.0))
        height = float(table.get("height", 1.0))
        _add_box(
            server,
            "environment/table_top",
            (length, depth, thickness),
            (cx, cy, top_z - thickness * 0.5),
            _rgb(table.get("top_color", [0.78, 0.70, 0.56]), (199, 179, 143)),
        )
        leg_color = _rgb(table.get("leg_color", [0.30, 0.24, 0.20]), (77, 61, 51))
        leg_size = max(0.045, min(0.09, min(length, depth) * 0.09))
        leg_height = max(0.1, height - thickness)
        for index, x_sign in enumerate((-1.0, 1.0)):
            for depth_index, y_sign in enumerate((-1.0, 1.0)):
                _add_box(
                    server,
                    f"environment/table_leg_{index * 2 + depth_index}",
                    (leg_size, leg_size, leg_height),
                    (
                        cx + x_sign * (length * 0.5 - leg_size),
                        cy + y_sign * (depth * 0.5 - leg_size),
                        top_z - thickness - leg_height * 0.5,
                    ),
                    leg_color,
                )
