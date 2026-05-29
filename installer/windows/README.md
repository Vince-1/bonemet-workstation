## Windows Setup.exe（A 路线：仅编译入口）

> 完整打包/安装/重装说明：[docs/PACKAGING.md](../../docs/PACKAGING.md)

目标：
- 用户拿到 **`Setup.exe`** 一键安装、开始菜单/桌面快捷方式、可卸载
- 运行时仍是 **pip 在线安装依赖**
- 可选加固：用 **Nuitka 只编译两个入口**（API/Worker），不改变其余源码结构

### 0. 前置
- Windows 打包机安装：
  - Inno Setup（提供 `iscc.exe`）
  - Windows SDK（提供 `signtool.exe`，用于签名）
- 打包机有网络（pip 下载依赖 / 时间戳签名）

### 1. 生成 release pack 目录
在仓库根目录（Linux/Windows 都可）：

```bash
make release-pack-windows
```

将生成：
- `dist-release/BoneMet-Workstation-<ver>-win-x64/`
- `dist-release/BoneMet-Workstation-<ver>-win-x64.zip`

### 一键执行（推荐）

在 Windows 打包机仓库根目录执行：

```powershell
installer\windows\one_click.ps1 -Version "<ver>" -IsccPath "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
```

如需签名：

```powershell
installer\windows\one_click.ps1 -Version "<ver>" -IsccPath "...\iscc.exe" -PfxPath ".\cert.pfx" -PfxPassword "******"
```

### 2. （可选）用 Nuitka 编译入口
在 Windows 上进入解压后的 release pack 目录：

```powershell
cd dist-release\BoneMet-Workstation-<ver>-win-x64
installer\windows\compile_nuitka.ps1
```

会产出：
- `bin\bonemet-api.exe`
- `bin\bonemet-worker.exe`

启动脚本已支持优先使用这些 exe（若存在）。

### 3. 生成 Setup.exe

```powershell
installer\windows\build_installer.ps1 -Version "<ver>" -IsccPath "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
```

输出：
- `dist-release/BoneMet-Workstation-<ver>-Setup.exe`

卸载 / 重新安装：
- **Setup.exe**：`unins000.exe` 或 **设置 → 应用**；**再次运行 Setup** 可升级/重装，向导默认 **保留数据、不保留模型、不重装 pip**
- **zip 安装**：`卸载.bat` / `重新安装.bat`；「安装并启动」已安装时 **S** 启动 / **R** 重新安装（可选数据/模型/依赖） / **N** 仅重装 pip
- **重装清理**：先解压新版本覆盖安装目录；重装时按 `.bonemet_manifest.json` 删除新包中不存在的旧程序文件（不删保留的 data/models、不删 pip 的 site-packages 除非勾选重装依赖）

### 4. （可选）签名 Setup.exe

```powershell
installer\windows\sign_installer.ps1 -Version "<ver>" -PfxPath "path\to\cert.pfx" -PfxPassword "******"
```

