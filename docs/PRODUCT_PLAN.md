# 产品阶段计划（独立工程视角）

> 完整背景与模块说明见 trains 仓内  
> `docs/plans/hospital_bone_met_deploy_plan_20260521.md`（研发汇报用）。  
> **本文件只保留 bonemet-workstation 仓库内要执行的交付项。**

## Phase 0 — 工程骨架

- [x] 独立目录 `bonemet-workstation/`  
- [x] 隔离策略 `docs/STANDALONE.md`  
- [x] 自包含 `schemas/`  
- [x] `bonemet_core`：ingest / pipeline / pairing / review_tasks / queue  
- [x] api：工作列表、病例详情、图像、review PATCH、签发、入队推理  
- [x] worker：消费 `queue/pending.jsonl`  
- [x] web：工作列表 + 双图复核（保存/签发/重跑）  
- [x] `scripts/setup_demo.py`、`docs/GETTING_STARTED.md`  

## Phase 1 — MVP 临床闭环

- [x] ingest API：`POST /api/ingest/dicom`、图像对导入  
- [x] worker 单 Job 流水线（检测 + 骨分割占位/ONNX + 配对 + 部位 + triage）  
- [x] 复核：框编辑 + 自动保存  
- [x] 报告：`report_zh.md` 模板 + **前端格式化预览** + 签发写 draft.md  
- [x] `docs/PENDING_USER_REVIEW.md` 待审核清单  

## Phase 2 — 试点运维（进行中）

- [x] 下一例 API 预取（web 轻量）  
- [x] 默认接受 AI 检出，无额外确认流程（R-16，2026-05-25）  
- [x] Worker 默认 `python-runtime`（`scripts/run_worker.sh`）  
- [x] Basic Auth（`config` 开关 + `apps/api/auth.py`）  
- [x] 夜间批处理脚本 `scripts/night_batch.py` / `make night-batch`  
- [x] 检测 ONNX 模型常驻（worker 进程内缓存）  
- [x] SQLite 病例索引 `data/cases/index.db`（`make rebuild-index`）  
- [x] 病灶轮廓自动提取 `lesion_contour.py`（阈值+形态学，2026-05-25）  
- [x] GPU 优先 + 自动空闲设备检测 `gpu_util.py`（`detect_device: auto`）  
- [x] 报告前端格式化预览 modal（不依赖 reportlab PDF）  
- [x] 框显示/隐藏切换按钮 + 快捷键 B  
- [x] 清除 demo mock 框（模板和数据均改为空 boxes）  
- [ ] Docker / 备份 runbook 细化（见 `DEPLOY.md` 草案）  
- [ ] PACS 目录监听脚本（`scripts/watch_pacs_inbox.py` 待加）  
- [ ] Redis 队列（配置占位，实现为 jsonl）  

## Phase 3 — 对接与合规

- PACS 监听 / 导出 approved（单向离线包）  

**不包含**：在本仓库内调用 trains 训练脚本或读取 `prediction/`。
