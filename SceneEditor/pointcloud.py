from __future__ import annotations

from pathlib import Path
from typing import List


def find_pointclouds(root: str | Path) -> List[Path]:
    base = Path(root)
    return sorted(path for suffix in ("*.ply", "*.pcd", "*.xyz", "*.xyzrgb") for path in base.rglob(suffix)) if base.exists() else []
