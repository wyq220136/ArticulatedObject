from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from DatasetGenerator.SceneEditor.config import load_config
    from DatasetGenerator.SceneEditor.windows.viser_app import run_app
else:
    from ..config import load_config
    from .viser_app import run_app


def main() -> None:
    parser = argparse.ArgumentParser("DatasetGenerator SceneEditor (Windows/Viser)")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1] / "config.yml"),
        help="SceneEditor YAML config path",
    )
    args = parser.parse_args()
    run_app(load_config(args.config))


if __name__ == "__main__":
    main()
