# 数据契约（产品内自包含副本）

与 trains 仓 `docs/schemas/` 保持 **概念一致**，但本目录为 BoneMet Workstation **唯一运行时契约来源**。

- 产品 **不读取** trains 下的 schema 路径。  
- 若研发侧更新契约，需 **手动同步副本** 到本目录并 bump `layout_version`。

文件：

- `box_v1.json` — 归一化检测框  
- `case_bundle_v1.json` — 临床 `case_bundle/{study_uid}/`  
- `dataset_layout_v2.json` — 可选：院内科研子集导出  
- `MIGRATION.md` — 分片与导出说明（无 trains 路径依赖）

校验（在产品根目录执行）：

```bash
python scripts/validate_case_bundle.py data/cases/case_bundle/STUDY_UID
```
