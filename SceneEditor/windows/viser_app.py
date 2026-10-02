from __future__ import annotations

from typing import Any

from ..viser_editor import run_app as _run_app


def run_app(config: dict[str, Any]) -> None:
    _run_app(config, platform_name="Windows")
