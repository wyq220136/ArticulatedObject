from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw


def _draw(image_path: Path, box: List[int] | None, output: Path, color: tuple[int, int, int], label: str, second_box: List[int] | None = None) -> None:
    image = Image.open(image_path).convert("RGB")
    if box:
        draw = ImageDraw.Draw(image)
        draw.rectangle(box, outline=color, width=max(2, image.width // 250))
        draw.text((box[0] + 4, box[1] + 4), label, fill=color)
        if second_box:
            draw.rectangle(second_box, outline=(230, 40, 180), width=max(2, image.width // 250))
            draw.text((second_box[0] + 4, second_box[1] + 4), "PERTURBED", fill=(230, 40, 180))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def make_visualizations(record: Dict[str, Any], root: Path) -> Dict[str, str]:
    scene = str(record["scene"])
    target = record["target"]
    folder = str(target["target_folder"])
    ref_box = target.get("reference_bbox_xyxy")
    inf_box = target.get("inference_bbox_xyxy")
    ref = root / "reference" / f"{scene}__reference__{folder}_refer.png"
    inf = root / "inference" / f"{scene}__inference__{folder}_gt_perturbed.png"
    _draw(Path(target["reference_rgb"]), ref_box, ref, (0, 210, 80), "GT")
    perturb = None
    if inf_box:
        dx = max(2, int((inf_box[2] - inf_box[0]) * 0.05))
        perturb = [inf_box[0] + dx, inf_box[1], inf_box[2] + dx, inf_box[3]]
    _draw(Path(target["inference_rgb"]), inf_box, inf, (0, 210, 80), "GT", perturb)
    return {"reference": str(ref), "inference": str(inf)}
