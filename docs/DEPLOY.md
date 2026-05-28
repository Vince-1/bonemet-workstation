# 院内部署

## 硬件建议

| 组件 | 最低 | 推荐 |
|------|------|------|
| GPU | 8GB 显存 | 12GB+，CUDA 11.8+ |
| CPU | 8 核 | 16 核 |
| 内存 | 32GB | 64GB |
| 磁盘 | 500GB SSD | 1TB+，`/var/lib/bonemet` 独立挂载 |

## 单机 Docker（推荐试点）

```bash
cd bonemet-workstation/deploy
cp .env.example .env
# 编辑 BONEMET_DATA_ROOT、模型路径、GPU

docker compose up -d
```

服务：

| 服务 | 端口 |
|------|------|
| web + api（Caddy） | 443 |
| worker | 无对外端口 |

## 裸机开发

```bash
conda activate python-runtime   # 与训练一致；勿用 trains/.conda（cu130 与驱动 11.8 不匹配）
make api
make worker   # 调用 scripts/run_worker.sh
make web
```

详见 [GETTING_STARTED.md](GETTING_STARTED.md)、休假交接 [VACATION_HANDOFF_20260522.md](VACATION_HANDOFF_20260522.md)。

## 模型安装

1. 将检测 `.onnx` 放入 `${BONEMET_DATA_ROOT}/models/detect/v1/` 等。  
2. 编辑 `data/models/registry.yaml`（或使用 `config/local.yaml` 中的路径）。  
3. `docker compose restart worker`。

## 备份

每日备份 `${BONEMET_DATA_ROOT}/cases` 与 `config/local.yaml`；模型目录可按版本归档。

## 升级

1. 拉取新版本镜像或代码。  
2. 运行 `scripts/migrate_data.py`（若有 schema 变更）。  
3. 蓝绿：新 worker 读新 `registry.yaml`，api 滚动重启。
