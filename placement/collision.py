from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np


def footprint(extent: Iterable[float], xy: Iterable[float], margin: float = 0.018) -> Tuple[float, float, float, float]:
    e = list(extent)
    x, y = list(xy)[:2]
    return float(x - e[0] * 0.5 - margin), float(x + e[0] * 0.5 + margin), float(y - e[1] * 0.5 - margin), float(y + e[1] * 0.5 + margin)


def overlaps(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def valid_position(box: Tuple[float, float, float, float], bounds: Tuple[float, float, float, float], placed: List[Tuple[float, float, float, float]]) -> bool:
    return box[0] >= bounds[0] and box[1] <= bounds[1] and box[2] >= bounds[2] and box[3] <= bounds[3] and not any(overlaps(box, item) for item in placed)


def repair_positions(extents: List[np.ndarray], seed: int, bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float]]:
    rng = np.random.default_rng(int(seed))
    placed: List[Tuple[float, float, float, float]] = []
    result: List[Tuple[float, float]] = []
    for extent in extents:
        accepted = None
        for _ in range(500):
            xy = (float(rng.uniform(bounds[0] + 0.1, bounds[1] - 0.1)), float(rng.uniform(bounds[2] + 0.08, bounds[3] - 0.08)))
            box = footprint(extent, xy)
            if valid_position(box, bounds, placed):
                accepted = xy
                placed.append(box)
                break
        if accepted is None:
            raise RuntimeError("unable to place all objects without footprint overlap")
        result.append(accepted)
    return result
