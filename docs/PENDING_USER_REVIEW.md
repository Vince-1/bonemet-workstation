# 待您审核 / 决策项

> 下列条目已由产品方 **2026-05-21** 确认；研发按决议实现。后续变更请新开条目。

| ID | 决议 | 实现要点 | 状态 |
|----|------|----------|------|
| R-01 | **检测主线 B（ONNX）** `1982single_cleaned_p0p1p2_p3first644_811_20260513_p5ft2_ft1280_continued_ep100`（ONNX 导出，含 NMS；与训练权重一致），`conf=0.24`，`imgsz=1280` | `scripts/install_models.sh` + `registry.yaml` | ✅ 已确认（2026-05-22 对齐主线 B） |
| R-02 | **骨分割 ONNX 拷贝至项目**；禁止引用 RadiSmart；预处理在 `bonemet_core` 内；**未配置禁止跑流水线**；**禁止几何退化** | `normalize.py` / `onnx_infer.py` / `validate.py` | ✅ 已确认 |
| R-03 | 报告含免责声明，科研辅助表述 | `templates/report_zh.md` | ✅ 已确认 |
| R-04 | DICOM：**单文件内含正反两层**（与 `prepare_sh_ruijin_wholebody_yolo.py` 一致，`DetectorVector`） | `dicom_io.py` / `ingest.py` | ✅ 已确认 |
| R-05 | **签发后允许再编辑** | `sign.lock_after_sign: false`（默认） | ✅ 已确认 |
| R-06 | 前期为 **科研辅助**，UI 固定免责声明 | Web 顶栏 + 报告模板 | ✅ 已确认 |
| R-07 | 导出 **含原图，暂不脱敏** | `export_approved` 整包 `copytree`（含 `images/`、`dicom/`） | ✅ 已确认 |
| R-08 | **单账号** Basic Auth 即可 | `auth.basic_enabled` 可选，环境变量覆盖密码 | ✅ 已确认 |
| R-09 | **不自动回流训练**，仅人工在 bonemet-ml 启动 | 无 workstation 触发器 | ✅ 已确认 |
| R-10 | 配对阈值 **暂用默认** `max_dist=0.12` | 未改代码 | ✅ 已确认 |

## 部署前检查清单

```bash
cd bonemet-workstation
make install-models   # 拷贝检测 ONNX + Big/Rib ONNX + Plans
make setup-demo       # 模型齐全时自动入队 pipeline
make check
```

`GET /health` 返回 `models.ok: true` 后方可导入并跑 worker。

## 运维说明（R-08）

试点环境在 `config/local.yaml` 设置：

```yaml
auth:
  basic_enabled: true
```

账号密码：`BONEMET_BASIC_USER` / `BONEMET_BASIC_PASSWORD` 或配置项 `basic_user` / `basic_password`。

---

## R-11～R-17 决议（2026-05-25 确认）

| ID | 决议 | 实现要点 | 状态 |
|----|------|----------|------|
| R-11 | **并存**：独立浏览器 + PACS 对接可并行，共用 `POST /api/ingest/dicom` | 文档对齐；PACS 监听脚本待院方目录 | ✅ 已确认 |
| R-12 | **暂不用 PDF**，Markdown 草稿 + 前端格式化预览 | 移除 PDF 签发提示；报告预览改 modal 渲染 | ✅ 已确认 |
| R-13 | **试点不脱敏**，正式入院前加脱敏层 | 同 R-07 | ✅ 已确认 |
| R-14 | **使用现有阈值+形态学轮廓**（`lesion_contour.py`，源自 `auto_clean_segment.py`），框内自动提取 | 已接入 pipeline，contour 写入 boxes JSON | ✅ 已确认 |
| R-15 | **GPU 优先 + 自动检测空闲设备**，失败回退 CPU | `detect_device: auto`；`gpu_util.py` | ✅ 已确认 |
| R-16 | **所有预测框默认写入报告**，无额外确认流程；侧栏不再显示待处理列表 | `build_review_tasks` 返回空；工作列表移除"待处理"列 | ✅ 已确认 |
| R-17 | **配对阈值根据数据调整**，不固定默认值 | 待试点数据抽检后再改参数 | ✅ 已确认 |

### 运维（可选确认）

- 试点是否开启 Basic Auth（`config/local.yaml` `auth.basic_enabled: true`）？
- 夜间批处理目录：是否由院方 IT 提供 PACS 落地路径对接 `night_batch.py`？

---

最后更新：2026-05-25（R-11～R-17 确认 + 轮廓/GPU/报告预览实现）
