# SceneEditor

The files in this directory are the platform-independent SceneEditor layer:

- `config.py` loads and normalizes the editor configuration.
- `asset_browser.py` discovers model directories.
- `scene_state.py` stores editable object transforms and joint values.
- `manifest.py` reads and writes the manifest contract.
- `pointcloud.py` contains point-cloud loading helpers.
- `environment.py` draws the shared tabletop.
- `preview.py` normalizes preview meshes to the configured object size.
- `pose.py` converts between the 9D editor pose and quaternions.

The default table is approximately `1 x 1 x 1` in scene units. Models are
normalized so their largest bounding-box axis is `0.10` by default; configure
`preview.object_max_extent` between `0.05` and `0.10` when a different ratio is
needed. SceneEditor exposes one uniform `scale` value and writes equal
`scale_xyz` components for manifest compatibility.

After selecting an object, Viser shows translation and rotation controls at the
same time. Selecting a movable part binds both controls to the SAPIEN link while
the effective motion remains constrained by the URDF joint. The resulting pose,
qpos, and part records are synchronized to the scene state and saved in the
manifest.
- `config.yml` is the shared editor configuration.

Set the `models` list in `config.yml` to the model directories needed for a
session, relative to `models_root`, for example `bottle/3517`. The editor only
opens those entries; an empty list intentionally exposes no models and does
not scan the complete Models directory. Structured entries are also supported:
`{category: bottle, instance: 3517}`.

Platform-specific launchers live under `linux/` and `windows/`. On Linux use
`linux/run.sh`; on Windows use `windows/run.ps1`. Both accept an optional path
to a config YAML file. Relative paths in that YAML file are resolved relative to
the YAML file itself, so the same manifest format can be used from any working
directory.
