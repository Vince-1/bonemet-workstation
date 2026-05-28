# 数据迁移：monolithic `data.json` ↔ 分片布局

> 配套脚本（Phase 0）：`scripts/schemas/chunk_data_json.py`（待实现）  
> Schema：[dataset_layout_v2.json](./dataset_layout_v2.json)、[case_bundle_v1.json](./case_bundle_v1.json)

## 1. 目标

| 方向 | 说明 |
|------|------|
| **chunk** | `prediction/<tag>/data.json` → `datasets/<tag>/`（manifest + index + patients/） |
| **export_case** | `case_bundle/{study_uid}/` → `datasets/<export_tag>/patients/{id}.json`（仅 `approved`） |
| **import_case** | 批量推理输出 → 直接写 `case_bundle/`，不经过大 JSON |

运行时 **禁止** 临床与新 SPA 读取 `data.json`；`_legacy.data.json` 仅给旧脚本可选生成。

## 2. Chunk 算法（`chunk_data_json.py`）

**输入**：`--data-json path/to/data.json`  
**输出**：`--out-dir datasets/<dataset_id>/`

1. 读取 `meta`、`patients[]`。  
2. 计算 `data_sha256 = SHA256( canonical_json(data.json) )`（或文件字节哈希，需在 manifest 注明）。  
3. 对每个 `patient`：
   - 写入 `patients/{patient_id}.json`，注入 `schema_version: patient_chunk_v2`。  
   - 累计 `counts`（gt/pred 前后数量）。  
4. 写 `index.json`（仅索引字段，无框坐标）。  
5. 写 `manifest.json`（含 `source_data_json`、`patients_count`、`chunks` 相对路径）。  
6. 若存在同级 `three_region_cache.bin`：按 patient 切分为 `cache/{patient_id}.region.bin`（格式与现 binary 编码一致，见 `three_region_cache_binary.py`）。  
7. 若存在 `stats.json`：生成 `stats.summary.json`（全局 KPI）；完整 per-patient stats 可选 `patients/{id}.stats.json`。  
8. **验收**：
   - `len(index.patients) == len(data.patients)`  
   - 随机抽 10 例：chunk 与原始 `patients[i]` 深比较一致（除 `schema_version`）  
   - `index.json` 体积应 **≪** `data.json`（通常 &lt; 5%）

**可选**：`--write-legacy-copy` 将原文件复制为 `_legacy.data.json`（不修改内容）。

## 3. 与 `case_bundle` 的字段映射

| case_bundle | patient_chunk / 备注 |
|-------------|----------------------|
| `inference/boxes_front.json` → `boxes[]` | `pred.front` |
| `inference/boxes_back.json` | `pred.back` |
| `review/boxes.json` | 导出时可写 `gt` 或单独 `review` 字段（训练导出策略见下） |
| `meta.study_uid` | 临床主键；导出时 `patient_id` 可与 study_uid 相同或映射表 |
| `images/*.webp` | `images.front/back` 路径改为 dataset 相对路径或复制资产 |

**训练回流（approved）**：

- 默认将 **`review/boxes.json`** 作为 YOLO 导出的 GT 来源（若 `negative_explicit` 则空标签）。  
- `inference/` 保留为 pred 存档，便于对比。

## 4. API 路径约定（实现参考）

| 研发 | 临床 |
|------|------|
| `GET /api/datasets` | `GET /api/cases?date=&status=` |
| `GET /api/datasets/{id}/index` | （列表由 SQLite 提供，index 可选缓存） |
| `GET /api/datasets/{id}/patients/{pid}` | `GET /api/cases/{study_uid}` |
| `PATCH /api/datasets/{id}/draft` | `PATCH /api/cases/{study_uid}/review` |

## 5. 回滚

保留原始 `data.json` 与 `.bak` 不删；分片目录可整体 `rm -rf` 后重新 chunk。  
`data_sha256` 不变则前端缓存 URL 不变。

## 6. 版本升级

| schema_version | 变更策略 |
|----------------|----------|
| `patient_chunk_v2` → v3 | 新字段 optional；读取方忽略未知字段 |
| `case_bundle_v1` → v2 | 同上；`meta.schema_version` 升级 |

破坏性变更需同时 bump `layout_version` 与 Chunk Builder 版本。
