# 运行时数据（不提交 Git）

部署时挂载到 `BONEMET_DATA_ROOT`，开发期默认为 `./data`。

```
data/
  cases/case_bundle/{study_uid}/   # 临床病例（见 schemas/case_bundle_v1.json）
  models/                          # 权重 + registry.yaml
  queue/                           # Job 状态
  logs/
  export/approved/                 # 可选：给研发的人工导出包
```

开发时可复制示例病例：

```bash
cp -r schemas/examples/case_bundle_minimal data/cases/case_bundle/STUDY_DEMO_001
# 并确保 meta.json 中 study_uid 与目录名一致
```
