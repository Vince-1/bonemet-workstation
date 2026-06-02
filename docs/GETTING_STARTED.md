# 本地运行（MVP）

## 1. 安装

```bash
cd bonemet-workstation
make install
```

## 2. 模型（必填，未配置禁止跑流水线）

```bash
make install-models   # 主线 B 检测 ONNX + Big/Rib ONNX + Plans → data/models/
```

若你手头只有检测 `best.pt`，可先导出成 workstation 使用的 `model.onnx`（打包时用；运行时不需要 torch）：

```bash
BONEMET_DETECT_PT=/path/to/best.pt make convert-detect-onnx
```

决议见 [PENDING_USER_REVIEW.md](PENDING_USER_REVIEW.md)（已全部确认）。

## 3. 演示数据 + 推理

```bash
make setup-demo    # 创建 STUDY_DEMO_001；模型齐全时自动入队
```

开三个终端：

```bash
make api      # http://localhost:10120
make worker   # 默认 python-runtime（见 scripts/run_worker.sh）
make web      # http://localhost:10123（默认轮询 watch，避免 ENOSPC）
```

若 `make web` 仍报 `ENOSPC: System limit for number of file watchers reached`，可临时提高上限（需 sudo）：

```bash
sudo sysctl -w fs.inotify.max_user_watches=524288
```

或手动：`cd apps/web && npm run dev:poll`（`make web` 已等价于 dev:poll）。

浏览器打开 http://localhost:10123：

- 工作列表顶部可填 **WholeBody DICOM 路径**（单 `.dcm` 含正反两层，或所在目录）  
- 点击病例进入复核：**拖拽**移动框、空白处**拖拽**新建框、**Del** 删除选中框  
- 修改后 **1.5s 自动保存**；也可点「立即保存」→「签发」

`GET /health` 中 `models.ok` 须为 `true`。推理仅依赖 ONNXRuntime（不再需要 torch/ultralytics）。安装脚本会优先尝试安装 `onnxruntime-gpu`，失败则回退 `onnxruntime`（CPU）。

### GPU / 环境说明

- 若安装了 `onnxruntime-gpu` 且机器 CUDA/驱动匹配，检测/骨分割可使用 GPU；否则自动使用 CPU。
- 配置里 `detect_device: cpu` 可强制使用 CPU（较慢）；GPU 失败时流水线会 **自动回退 CPU**。
- 推荐启动 worker：

```bash
# 示例：使用项目 venv / 内置 python 均可
cd bonemet-workstation && PYTHONPATH=packages python -m apps.worker.main
```

## 4. 导出 PDF 报告

审阅页工具栏 **PDF** 按钮，或报告预览弹窗 **导出 PDF**，将下载当前病例的格式化中文报告。批量导出 zip 时也会附带 `report/report.pdf`。

## 5. 导出给 bonemet-ml（含原图，暂不脱敏）

```bash
python scripts/export_approved.py --export-id batch_001
# 拷贝 data/export/approved/batch_001 → bonemet-ml/data/imports/
```

## 6. 导出/导入（Workstation 间迁移）

### 导出

在工作列表页可调用 API 导出（zip）：
- `POST /api/cases/export`

### 导入

将导出的 zip 上传回 workstation：
- `POST /api/cases/import`（multipart/form-data，字段名 `file`；可选 `force=true` 覆盖同名病例）
