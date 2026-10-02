from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw


def bbox(mask: np.ndarray) -> List[int] | None:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def evaluate(entry: Dict[str, Any], min_pixels: int, min_fill: float) -> Tuple[bool, Dict[str, Any]]:
    quality: Dict[str, Any] = {"targets": []}
    ok = True
    image_area = max(1, int(entry.get("width", 1)) * int(entry.get("height", 1)))
    for target in entry.get("targets", []):
        mask_path = Path(str(target.get("mask", "")))
        mask = np.asarray(Image.open(mask_path)) if mask_path.exists() else np.zeros((1, 1), dtype=np.uint8)
        pixels = int(np.count_nonzero(mask))
        box = bbox(mask)
        fill = float(pixels / image_area)
        quality["targets"].append({"target_folder": target.get("target_folder"), "mask_pixels": pixels, "mask_bbox_xyxy": box, "framing_fill": fill})
        ok = ok and pixels >= int(min_pixels) and fill >= float(min_fill)
    entry["quality"] = quality
    return ok, quality


def draw_overlay(rgb_path: Path, bbox_xyxy: List[int] | None, output: Path, color: Tuple[int, int, int]) -> None:
    image = Image.open(rgb_path).convert("RGB")
    if bbox_xyxy:
        ImageDraw.Draw(image).rectangle(bbox_xyxy, outline=color, width=max(2, image.width // 250))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
