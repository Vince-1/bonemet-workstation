# GitHub Release 发版（不含模型）

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

说明：
- Release 包默认 **不包含模型**（CI 固定 `BUNDLE_MODELS=0`）
- 首次运行依赖仍通过 pip 在线安装

### 方式 B：手动触发 workflow（无 tag）

在 GitHub Actions 页面手动运行 `release` workflow，并填写 `version`（例如 `0.2.1`）。

## 2. 维护者：模型包如何挂到同一个 Release

建议把模型打成一个 zip（目录结构保持与 `data/models/` 一致）：

```
data/models/
  registry.yaml
  detect/v1/model.onnx
  bone_big/...
  bone_axis/...
```

zip 命名建议：
- `BoneMet-Models-0.2.1.zip`（或包含模型版本号）

然后把该 zip **作为 Release asset 上传**。

> 备注：模型 zip 不放入 git 历史，避免仓库膨胀与清理困难。

## 3. 用户：如何使用 Release 交付包

### Windows

1) 下载并解压：
- `BoneMet-Workstation-<ver>-win-x64.zip`

2) 下载并解压模型包到同一目录下（让 `data/models/registry.yaml` 存在）

3) 双击：
- `安装并启动.bat`

### Linux

1) 解压：
- `BoneMet-Workstation-<ver>-linux-x64.tar.gz`

2) 解压模型包到同一目录下（让 `data/models/registry.yaml` 存在）

3) 双击：
- `安装并启动.sh`

