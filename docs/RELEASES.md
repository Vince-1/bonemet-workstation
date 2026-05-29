# GitHub Release 发版（不含模型）

> 本地院内打包（默认含模型、可选 Setup）见 [PACKAGING.md](PACKAGING.md)。

目标：
- 代码仓库不包含模型文件（`data/models/**` 被忽略）
- GitHub Actions 在打 tag 后自动构建交付包并上传到 Release
- 用户从同一个 Release 页面下载：
  - 程序包（Windows `.zip` / Linux `.tar.gz`）
  - 模型包（单独上传的 `BoneMet-Models-*.zip`，见下）

## 1. 维护者：如何发布程序包

### 方式 A：打 tag 自动发布（推荐）

在仓库根目录：

```bash
git tag v0.2.1
git push origin v0.2.1
```

GitHub Actions 会自动生成并上传：
- `dist-release/BoneMet-Workstation-0.2.1-win-x64.zip`
- `dist-release/BoneMet-Workstation-0.2.1-linux-x64.tar.gz`
- `dist-release/BoneMet-Workstation-0.2.1-Setup.exe`（Windows job，`BUNDLE_MODELS=0`）

说明：
- Release 包默认 **不包含模型**（CI 固定 `BUNDLE_MODELS=0`）
- 含 `.bonemet_manifest.json`（重装升级时清理旧程序文件）
- 首次运行依赖仍通过 pip 在线安装

### 方式 B：手动触发 workflow（无 tag）

在 GitHub Actions 页面手动运行 `release` workflow，并填写 `version`（例如 `0.2.1`）。

## 2. 维护者：模型包如何挂到同一个 Release

建议把模型打成一个 zip（目录结构保持与 `data/models/` 一致）。仓库已提供脚本：

```bash
BONEMET_VERSION=0.2.1 make models-zip
```

产物：
- `dist-release/BoneMet-Models-0.2.1.zip`

zip 内部结构：

```
data/models/
  registry.yaml
  detect/model.onnx
  bone_seg/Big.onnx
  bone_seg/Rib.onnx
  bone_seg/BigPlans.json
  bone_seg/RibPlans.json
```

zip 命名建议：
- `BoneMet-Models-0.2.1.zip`（或包含模型版本号）

然后把该 zip **作为 Release asset 上传**：

```bash
scripts/upload_release_asset.sh v0.2.1 dist-release/BoneMet-Models-0.2.1.zip
```

> 备注：模型 zip 不放入 git 历史，避免仓库膨胀与清理困难。

## 3. 用户：如何使用 Release 交付包

### Windows

**方式 A：zip**

1) 下载并解压：`BoneMet-Workstation-<ver>-win-x64.zip`  
2) 下载并解压模型包到同一目录（`data/models/registry.yaml` 存在）  
3) 双击 `安装并启动.bat`  

**方式 B：Setup.exe**

1) 运行 `BoneMet-Workstation-<ver>-Setup.exe`（可选安装目录）  
2) 若无模型，同样解压模型包到安装目录  
3) 按向导完成；升级时再次运行新版 Setup，默认保留数据、不保留模型、不重装 pip  

卸载：`设置 → 应用`，或安装目录 `unins000.exe`。详见 [DESKTOP.md](DESKTOP.md)。

### Linux

1) 解压：
- `BoneMet-Workstation-<ver>-linux-x64.tar.gz`

2) 解压模型包到同一目录下（让 `data/models/registry.yaml` 存在）

3) 双击：
- `安装并启动.sh`

