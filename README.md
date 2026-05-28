# BoneMet Workstation — 骨转移辅助诊断软件（独立产品）

医院部署用 **全身骨显像 2D 前后位** 辅助诊断工作站。本目录为 **独立产品工程**，与仓库内 `web/apfusion`、`web/delta-studio`、`trains/src` 等研发资产 **无运行时依赖、无路径耦合**。

## 独立性说明

| 项目 | 本工程 | 原 `trains` 研发树 |
|------|--------|-------------------|
| 代码引用 | 禁止 `import` / 读取 trains 路径 | 继续用于实验与训练 |
| 数据目录 | `BONEMET_DATA_ROOT`（默认 `./data`） | `WB2D`、`prediction/` 等 |
| 模型权重 | `data/models/registry.yaml` 登记 | `runs/`、`artifacts/` |
| 病例存储 | `data/cases/case_bundle/` | 不参与 |
| 配置 | `config/*.yaml` + 环境变量 | 不读取 trains 配置 |

院内 approved 数据的训练与发版在独立工程 **[bonemet-ml](../bonemet-ml/)** 完成；临床侧仅通过 **export → 拷贝权重** 衔接，不经过 trains 数据集。

## 目录结构

```
bonemet-workstation/
├── README.md                 # 本文件
├── docs/                     # 产品文档（部署、架构、隔离策略）
├── schemas/                  # 数据契约（自包含副本）
├── config/                   # 默认配置模板
├── apps/
│   ├── api/                  # FastAPI 临床 API
│   ├── worker/               # GPU 流水线 Worker
│   └── web/                  # Vite 医生 SPA
├── packages/
│   └── bonemet_core/         # 共享 Python 库（预处理、推理、骨匹配）
├── deploy/                   # Docker / 安装脚本
├── scripts/                  # CLI：ingest、chunk、校验
└── data/                     # 运行时数据（gitignore，部署时挂载）
    ├── cases/
    └── models/
```

## 快速开始

**科室部署（无需命令行）：**

1. 研发机先 `make install-models`（若尚未安装），再打包（**默认预置 AI 模型**，约 600MB+）  
   - Linux：`make release-pack` → `.tar.gz`  
   - Windows：`make release-pack-windows` → `.zip`  
   - 双平台：`make release-pack-all`  
2. 用户解压后 **双击「安装并启动」/「安装并启动.bat」** 即可  

详见 [docs/DESKTOP.md](docs/DESKTOP.md)。

**本机开发调试：**

```bash
make install-desktop && make install-models
./安装并启动.sh    # 或 make launch
```

**开发（三终端、热更新）：**

```bash
make install && make setup-demo
make api · make worker · make web  → http://localhost:5173
```

详见 [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)。

## 文档索引

- [docs/STANDALONE.md](docs/STANDALONE.md) — 与 trains 隔离边界、资产迁移方式  
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 模块与数据流  
- [docs/DESKTOP.md](docs/DESKTOP.md) — **一键安装 / 启动（桌面模式）**
- [docs/DEPLOY.md](docs/DEPLOY.md) — 院内单机部署（Docker）  
- [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md) — 功能阶段（从医院计划摘编的产品视角）  
- [docs/PENDING_USER_REVIEW.md](docs/PENDING_USER_REVIEW.md) — **待您审核项（模型/文案/合规等）**  
- [schemas/README.md](schemas/README.md) — `case_bundle` / 数据分片契约  
- [bonemet-ml](../bonemet-ml/) — approved 回流训练（方案 B 独立实验室）  

## 许可证与仓库

当前置于 `trains/bonemet-workstation/` 便于与算法研发同仓协作；**发布院内版本时可整目录拆为独立 Git 仓库**，不影响 trains 其它目录。
