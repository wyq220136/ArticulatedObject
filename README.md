# DatasetGenerator 操作指南 / DatasetGenerator User Guide

本文档对应当前仓库中的 DatasetGenerator 实现。命令均从仓库根目录执行；Linux/macOS 使用 Bash，Windows 使用 PowerShell。

This guide describes the current DatasetGenerator implementation. Commands are run from the repository root; Linux/macOS examples use Bash and Windows examples use PowerShell.

---

# 中文指南

## 1. 两种使用模式

DatasetGenerator 支持两条互补的场景生成路线。

### 模式 A：直接提供参数化配置

用户准备 JSON、YAML 或 YML 配置，然后执行 DatasetGenerator/run.py：

~~~text
参数化 JSON/YAML
        |
        v
DatasetGenerator/run.py
        |
        +-- 场景布局生成
        +-- 物体放置与冲突规避
        +-- SAPIEN 渲染
        +-- RGB / depth / object mask / part mask 导出
        +-- pose / bbox / articulation annotation 导出
        +-- 数据集归档与索引
~~~

这种模式适合批量生成。场景规模、每个场景的目标物体数量、view 数量、相机、渲染质量和物体归一化都由 DatasetGenerator 配置控制。

### 模式 B：通过 Viser 配置 manifest

先在 SceneEditor 中编辑 3D 场景并保存 manifest.json，再交给同一个入口：

~~~text
SceneEditor (Viser)
        |
        +-- manifest.json
                |
                v
DatasetGenerator/run.py --manifest manifest.json
                |
                +-- SAPIEN 渲染与数据集导出
~~~

三类文件职责不同：

| 文件 | 作用 |
| --- | --- |
| DatasetGenerator/configs/config.yml | 数据集规模、输出目录、相机、渲染、质量和归一化 |
| DatasetGenerator/SceneEditor/config.yml | Viser 模型白名单、manifest 输出目录、预览尺寸、host 和 port |
| SceneEditor manifest.json | 一个具体场景的物体、位姿、缩放和 articulation 状态 |

## 2. manifest 结构

SceneEditor manifest 使用 schema dataset_generator_scene_manifest_v1。实际保存时 parts 会包含所有可动 part。

~~~json
{
  "schema": "dataset_generator_scene_manifest_v1",
  "scene": {"name": "scene_000", "profile": "interactive_scene"},
  "models_root": "/research/sapien/Models",
  "table": {},
  "camera": {},
  "objects": [
    {
      "slot": 0,
      "object": "bottle_3517",
      "category": "bottle",
      "source_dir": "/research/sapien/Models/bottle/3517",
      "urdf": "/research/sapien/Models/bottle/3517/mobility.urdf",
      "loader_scale": 0.12,
      "pose": {
        "translation_xyz": [0.0, 0.0, 0.05],
        "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
        "yaw_rad": 0.0,
        "scale_xyz": [1.0, 1.0, 1.0]
      },
      "qpos": [0.0],
      "articulation": {
        "qpos": [0.0],
        "selected_part_id": 8,
        "parts": [
          {
            "part_id": 8,
            "part_name": "lid",
            "link_name": "link_0",
            "joint_name": "joint_0",
            "joint_type": "continuous",
            "qpos_index": 0,
            "limits": [-3.14, 3.14],
            "pose_world": {
              "translation_xyz": [0.0, 0.0, 0.1],
              "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]
            }
          }
        ]
      },
      "is_target": true
    }
  ]
}
~~~

字段说明：

- schema 必须为 dataset_generator_scene_manifest_v1。
- scene.name 是输出 scene 名称。
- models_root、source_dir、urdf 必须在运行机器上可访问。
- table 描述桌面和桌腿；SceneEditor 默认桌面约为 1 x 1 x 1。
- camera 是可选相机配置；未提供时使用 DatasetGenerator 配置。
- objects 中每个 slot 必须唯一。
- pose.translation_xyz 和 pose.quaternion_wxyz 是物体世界位姿。
- pose.yaw_rad 是旧布局兼容字段；界面中的 scale 是统一缩放值，manifest 仍以三个相同的 scale_xyz 分量保存，默认 [1, 1, 1]。
- 界面中的 rotation_rpy_deg 是 R/P/Y 编辑输入；当前保存结果以 quaternion_wxyz 和 yaw_rad 为准，外部 manifest 可额外保留 rpy_deg 供阅读。
- loader_scale 是模型基础归一化缩放。
- qpos 和 articulation.qpos 是完整 SAPIEN articulation 状态。
- articulation.parts 保存 part/link/joint 映射、joint 类型、qpos 索引、限位和世界位姿。
- selected_part_id 只记录最后的 UI 选择，不会删除其它 part。
- is_target 指示物体是否作为目标。

## 3. 通过 Viser 生成布局

### 3.1 SceneEditor 配置

文件位置：

~~~text
DatasetGenerator/SceneEditor/config.yml
~~~

示例：

~~~yaml
models_root: /research/sapien/Models
manifest_output_dir: /research/iclr/scene_manifests

models:
  - bottle/3517
  - box/100189
  - kettle/3971

preview:
  object_max_extent: 0.10

host: 127.0.0.1
port: 8080
~~~

- models_root：Models 根目录。
- manifest_output_dir：Save manifest 的输出目录。
- models：启动时加载的白名单；支持 bottle/3517，也支持 category/instance 结构化条目。空列表不会扫描整个 Models 目录。
- 模型目录通常需要 mobility.urdf、mobility_v2.json 和 URDF 引用的 mesh。
- preview.object_max_extent：预览归一化最大 bbox，当前范围为 0.05 到 0.10。
- host、port：Viser 地址；相对路径按 YAML 文件目录解析。

### 3.2 Linux 路线

~~~bash
conda activate sapien
python -c "import yaml, trimesh, viser; print('dependencies ok')"
export PYTHON_BIN=/path/to/conda/envs/sapien/bin/python
cd /path/to/iclr
./DatasetGenerator/SceneEditor/linux/run.sh
~~~

指定配置：

~~~bash
./DatasetGenerator/SceneEditor/linux/run.sh ./DatasetGenerator/SceneEditor/config.yml
~~~

等价 Python 命令：

~~~bash
$PYTHON_BIN DatasetGenerator/SceneEditor/linux/run.py DatasetGenerator/SceneEditor/config.yml
~~~

终端会打印 Viser URL，通常为 http://127.0.0.1:8080。界面中可以添加/删除白名单物体，编辑 position_xyz、rotation_rpy_deg 和统一 scale，同时使用平移和旋转控件，选择 movable_part，并保存 manifest。scale 会同时作用于物体和所有 movable part；revolute/continuous part 只沿关节轴响应旋转，prismatic part 只沿关节轴响应平移，qpos 按 joint limits 截断。

### 3.3 Windows 路线

~~~powershell
conda activate sapien
python -c "import yaml, trimesh, viser; print('dependencies ok')"
$env:PYTHON_BIN = "\your_conda_path\anaconda\envs\your_env\python.exe"
.\DatasetGenerator\SceneEditor\windows\run.ps1
~~~

指定配置：

~~~powershell
.\DatasetGenerator\SceneEditor\windows\run.ps1 .\DatasetGenerator\SceneEditor\config.yml
~~~

等价 Python 命令：

~~~powershell
python DatasetGenerator\SceneEditor\windows\run.py DatasetGenerator\SceneEditor\config.yml
~~~

若 PowerShell 禁止脚本：

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
.\DatasetGenerator\SceneEditor\windows\run.ps1
~~~

Windows SceneEditor 负责布局编辑和 manifest 保存，不会自动启动后续数据集渲染；渲染统一执行 DatasetGenerator/run.py。

## 4. 直接使用 JSON/YAML 生成数据集

当前数据生成入口是 DatasetGenerator/run.py，接受 .json、.yml 和 .yaml。仓库现有默认配置是 DatasetGenerator/configs/config.yml。

Linux/macOS：

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/config.yml --overwrite
~~~

Windows：

~~~powershell
python DatasetGenerator\run.py DatasetGenerator\configs\config.yml --overwrite
~~~

常用配置：

~~~yaml
output_root: ../SimDataset
models_root: /path/to/your/models
seed: 1234
pair_count: 50
targets_per_scene: 2
views_per_scene: 20
candidate_slack: 20

render:
  render_scale: 0.75
  timeout_sec: 150
  width: 1920
  height: 1080

normalization:
  enabled: true
  target_max_extent: 0.14
  min_scale: 0.02
  max_scale: 1.0
~~~

- output_root：输出根目录。
- models_root：SAPIEN Models 根目录。
- seed：随机种子。
- pair_count：自动规划的场景/候选规模。
- targets_per_scene：每个场景的目标物体数。
- views_per_scene：每个 scene 的 viewpoint/articulation state 数量，默认 20。
- candidate_slack：候选布局额外数量。
- render：渲染比例、超时和分辨率。
- camera：相机、桌面朝向、视场角和 framing。
- scene_policy：杂物数量和目标 part 策略。
- normalization：物体 bbox 归一化。
- quality：目标像素和构图阈值。
- --overwrite：删除并重建已有 output_root，使用前确认目录。

JSON 使用相同字段。例如保存为 DatasetGenerator/configs/my_dataset.json：

~~~json
{
  "output_root": "../SimDataset",
  "models_root": "/path/to/your/models",
  "seed": 1234,
  "pair_count": 50,
  "targets_per_scene": 2,
  "views_per_scene": 20,
  "candidate_slack": 20,
  "render": {
    "render_scale": 0.75,
    "timeout_sec": 150,
    "width": 1920,
    "height": 1080
  }
}
~~~

运行：

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/my_dataset.json --overwrite
~~~

## 5. 使用 manifest 运行数据生成

假设 Viser 已保存 /scene_manifests/scene_000.json。

Linux/macOS：

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/config.yml --manifest /scene_manifests/scene_000.json --overwrite
~~~

Windows：

~~~powershell
python DatasetGenerator\run.py DatasetGenerator\configs\config.yml --manifest \scene_manifests\scene_000.json --overwrite
~~~

规则：

- --manifest 使用 manifest 中的物体和布局，覆盖自动场景规划。
- 仍需 DatasetGenerator 配置，因为渲染、输出目录、相机默认值和 views_per_scene 由它控制。
- manifest 模式规划一个场景，并生成配置指定数量的帧。
- pose、scale_xyz、qpos 和 articulation metadata 会进入布局记录。
- 运行前确认 source_dir、urdf、mobility_v2.json 和 mesh 可访问。

## 6. 输出结构与检查

~~~text
SimDataset/
├── manifest.json
├── render_batch_index.json
├── json/
│   ├── candidate_index.json
│   └── scene_000.json
├── multimodal/
│   └── scene_000/
│       ├── camera/intrinsics.json
│       ├── model/<object>/<part>/*.{obj,mtl,...}
│       ├── frames/
│       │   ├── frame_000/
│       │   │   ├── rgb.png
│       │   │   ├── depth.png
│       │   │   ├── object_masks/
│       │   │   ├── part_masks/
│       │   │   ├── annotations.json
│       │   │   └── mask_index.json
│       │   └── frame_019/
│       └── manifest.json
└── visualization/
~~~

至少检查：manifest.json 和 render_batch_index.json 存在；每个 scene 有 views_per_scene 个 frame；每帧都有 RGB、depth、object mask、part mask 和 annotations；camera/intrinsics.json 与 model 在 scene 级共享；annotation 中有 pose、bbox、qpos 或对应索引；终端报告的 scene/frame 数量符合预期。

---

# English Guide

## 1. Two usage modes

DatasetGenerator provides two complementary routes.

### Mode A: direct parameterized configuration

Prepare a JSON, YAML, or YML configuration and run DatasetGenerator/run.py:

~~~text
Parameterized JSON/YAML
        |
        v
DatasetGenerator/run.py
        |
        +-- scene layout generation
        +-- object placement and collision avoidance
        +-- SAPIEN rendering
        +-- RGB / depth / object mask / part mask export
        +-- pose / bbox / articulation annotation export
        +-- dataset archive and index generation
~~~

This mode is intended for batch generation. DatasetGenerator configuration controls dataset scale, target-object count, frame count, camera, rendering quality, and normalization.

### Mode B: configure a manifest with Viser

Edit a 3D scene in SceneEditor, save manifest.json, and pass it to the same entry point:

~~~text
SceneEditor (Viser)
        |
        +-- manifest.json
                |
                v
DatasetGenerator/run.py --manifest manifest.json
                |
                +-- SAPIEN rendering and dataset export
~~~

Keep these files separate:

| File | Purpose |
| --- | --- |
| DatasetGenerator/configs/config.yml | Dataset size, output, camera, rendering, quality, and normalization |
| DatasetGenerator/SceneEditor/config.yml | SceneEditor model allowlist, manifest output directory, preview size, host, and port |
| SceneEditor manifest.json | Object layout, pose, scale, and articulation state for one scene |

## 2. Manifest structure

SceneEditor writes dataset_generator_scene_manifest_v1. The Chinese section contains a complete compact example; a real manifest includes every detected movable part in articulation.parts.

Important fields:

- schema must be dataset_generator_scene_manifest_v1.
- scene.name becomes the generated scene name.
- models_root, source_dir, and urdf must resolve to readable assets and meshes.
- table describes the shared tabletop and legs; the default table is approximately 1 x 1 x 1.
- camera optionally overrides camera information.
- Every object slot must be unique.
- pose.translation_xyz and pose.quaternion_wxyz define the object world pose.
- pose.yaw_rad is retained for compatibility; the UI uses one uniform scale value and writes equal scale_xyz components for compatibility.
- rotation_rpy_deg is the UI input representation; saved state is driven by quaternion_wxyz and yaw_rad. An external manifest may additionally keep rpy_deg for readability.
- loader_scale is the base model normalization scale.
- qpos and articulation.qpos contain the complete SAPIEN articulation state.
- articulation.parts records part/link/joint mapping, joint type, qpos index, limits, and world pose.
- selected_part_id records only the last UI selection.

## 3. Configure a layout with Viser

### 3.1 SceneEditor configuration

The shared configuration is DatasetGenerator/SceneEditor/config.yml. Its main fields are models_root, manifest_output_dir, models, preview.object_max_extent, host, and port. models is a startup allowlist and does not scan the complete Models directory. Model directories normally need mobility.urdf, mobility_v2.json, and referenced meshes. Relative paths are resolved relative to the YAML file.

### 3.2 Linux route

~~~bash
conda activate sapien
python -c "import yaml, trimesh, viser; print('dependencies ok')"
export PYTHON_BIN=/path/to/conda/envs/sapien/bin/python
cd /path/to/iclr
./DatasetGenerator/SceneEditor/linux/run.sh
~~~

Explicit configuration:

~~~bash
./DatasetGenerator/SceneEditor/linux/run.sh ./DatasetGenerator/SceneEditor/config.yml
~~~

Equivalent Python invocation:

~~~bash
$PYTHON_BIN DatasetGenerator/SceneEditor/linux/run.py DatasetGenerator/SceneEditor/config.yml
~~~

Open the Viser URL printed by the terminal, normally http://127.0.0.1:8080. The UI supports allowlisted object insertion/deletion, position/RPY/uniform-scale editing, simultaneous translation and rotation controls, movable-part selection, and manifest saving. Uniform scale is applied to both the object and all movable parts. Revolute/continuous parts respond to rotation around their joint axis; prismatic parts respond to translation along their joint axis.

### 3.3 Windows route

~~~powershell
conda activate sapien
python -c "import yaml, trimesh, viser; print('dependencies ok')"
$env:PYTHON_BIN = "D:\term_files\anaconda\envs\sapien\python.exe"
.\DatasetGenerator\SceneEditor\windows\run.ps1
~~~

Explicit configuration:

~~~powershell
.\DatasetGenerator\SceneEditor\windows\run.ps1 .\DatasetGenerator\SceneEditor\config.yml
~~~

Equivalent Python invocation:

~~~powershell
python DatasetGenerator\SceneEditor\windows\run.py DatasetGenerator\SceneEditor\config.yml
~~~

If PowerShell blocks local scripts:

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
.\DatasetGenerator\SceneEditor\windows\run.ps1
~~~

The Windows editor has the same interactive layout and manifest-saving behavior as Linux. It does not automatically launch dataset rendering; run DatasetGenerator/run.py separately.

## 4. Generate a dataset directly from JSON/YAML

The only data-generation entry point is DatasetGenerator/run.py. It accepts .json, .yml, and .yaml. The current repository configuration is DatasetGenerator/configs/config.yml.

Linux/macOS:

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/config.yml --overwrite
~~~

Windows:

~~~powershell
python DatasetGenerator\run.py DatasetGenerator\configs\config.yml --overwrite
~~~

Important fields are output_root, models_root, seed, pair_count, targets_per_scene, views_per_scene, render, camera, scene_policy, normalization, and quality. views_per_scene defaults to 20. --overwrite rebuilds an existing output root, so verify the path first.

The JSON form uses the same keys. Save the equivalent JSON as DatasetGenerator/configs/my_dataset.json and run:

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/my_dataset.json --overwrite
~~~

## 5. Generate a dataset from a manifest

Assume Viser saved /research/iclr/scene_manifests/scene_000.json.

Linux/macOS:

~~~bash
python DatasetGenerator/run.py DatasetGenerator/configs/config.yml --manifest /research/iclr/scene_manifests/scene_000.json --overwrite
~~~

Windows:

~~~powershell
python DatasetGenerator\run.py DatasetGenerator\configs\config.yml --manifest D:\research\iclr\scene_manifests\scene_000.json --overwrite
~~~

The manifest replaces automatic scene planning. A DatasetGenerator configuration is still required because it controls rendering, output, camera defaults, and views_per_scene. Manifest mode plans one scene and generates the configured number of frames. Verify source_dir, urdf, mobility_v2.json, and all referenced meshes before running.

## 6. Output structure and validation

~~~text
SimDataset/
├── manifest.json
├── render_batch_index.json
├── json/
│   ├── candidate_index.json
│   └── scene_000.json
├── multimodal/
│   └── scene_000/
│       ├── camera/intrinsics.json
│       ├── model/<object>/<part>/*.{obj,mtl,...}
│       ├── frames/
│       │   ├── frame_000/
│       │   │   ├── rgb.png
│       │   │   ├── depth.png
│       │   │   ├── object_masks/
│       │   │   ├── part_masks/
│       │   │   ├── annotations.json
│       │   │   └── mask_index.json
│       │   └── frame_019/
│       └── manifest.json
└── visualization/
~~~

Verify that manifest.json and render_batch_index.json exist, every scene has views_per_scene frame directories, every frame contains RGB/depth/object-mask/part-mask/annotation outputs, camera intrinsics and model meshes are shared at scene level, and reported scene/frame counts match the requested configuration.
