# 休假交接进度（2026-05-22）

> 用户休假期间由研发继续推进；**需您归来后审核**的条目见 [PENDING_USER_REVIEW.md](PENDING_USER_REVIEW.md) §「休假归来待审」。

## 当前可运行状态（MVP）

| 组件 | 状态 | 说明 |
|------|------|------|
| `make api` | ✅ | FastAPI :8080 |
| `make worker` | ✅ | **默认** `scripts/run_worker.sh` → `python-runtime` |
| `make web` | ✅ | :5173 |
| 主线 B YOLO | ✅ | `install_models.sh` + registry |
| 复核 SPA | ✅ | 单屏双图、框编辑、自动保存、签发 |
| DICOM 导入 | ✅ | 单文件正反两层 |
| approved 导出 | ✅ | `export_approved.py` → bonemet-ml `imports/` |

**本地三连（请用 python-runtime，勿用 `trains/.conda`）**：

```bash
conda activate python-runtime
cd /home/wenhao/trains/bonemet-workstation
make install-models   # 若尚未安装权重
make api              # 终端 1
make worker           # 终端 2（已绑定 python-runtime）
make web              # 终端 3
```

## 本批已推进（无需您在线）

1. **「接受其余 AI」** — `POST /api/cases/{uid}/review/accept-rest` + 复核侧栏按钮；隐藏低置信/未配对 triage，保留须写入报告项。
2. **Worker 环境固定** — `make worker` → `scripts/run_worker.sh`；`.vscode` 默认解释器 `python-runtime`。
3. **文档** — 本交接页、`PENDING_USER_REVIEW` 待审表、部署计划 §12 进度勾选。

## 下一批（研发可继续做，不阻塞试点）

| 项 | 优先级 | 说明 |
|----|--------|------|
| SQLite 病例索引 | ✅ | `index.db` + API 启动自动 `ensure_index` |
| Redis 队列 | P2 | 配置有项，实现仍为 `pending.jsonl` |
| 模型常驻 / GPU 双 stream | 部分 | YOLO 已进程内缓存；骨分割 ONNX 仍每例加载 |
| 病灶轮廓惰性生成 | P3 | 计划 §0.3 |
| Docker 镜像内 CUDA 版本 | P2 | 需与院内部署驱动对齐 |
| bonemet-ml `make train` | P2 | 仍为 TODO 占位，import 链路已通 |

## 归来后建议操作（5 分钟）

1. 打开 http://localhost:5173 ，导入或打开已有病例，点 **接受其余 AI** 看 triage 是否符合预期。
2. `GET http://localhost:8080/health` 确认 `models.ok: true`。
3. 审阅 [PENDING_USER_REVIEW.md](PENDING_USER_REVIEW.md) 中 **R-11～R-15**（院方形态、报告回写、脱敏等）。
4. 若需 GPU：`config/local.yaml` 设 `detect_device: "0"`，worker 必须在 `python-runtime` 下运行。

## 参考

- 总计划：`docs/plans/hospital_bone_met_deploy_plan_20260521.md`
- 产品阶段：`docs/PRODUCT_PLAN.md`
