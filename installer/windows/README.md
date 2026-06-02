## Windows Setup.exe（A 路线：仅编译入口）

> 完整打包/安装/重装说明：[docs/PACKAGING.md](../../docs/PACKAGING.md)

目标：
- 用户拿到 **`Setup.exe`** 一键安装、开始菜单/桌面快捷方式、可卸载
- 运行时仍是 **pip 在线安装依赖**
- 可选加固：用 **Nuitka 只编译两个入口**（API/Worker），不改变其余源码结构

### 0. 应用图标

生成 `bonemet.ico` / `bonemet.png` 并放入本目录，见 **[ICON.md](ICON.md)**（含 AI 绘图提示词）。打 release 包时会复制到安装目录。

### 1. 前置
- Windows 打包机安装：
  - **Inno Setup 6**（`ISCC.exe` 在 PATH 或默认目录；非默认路径设 `$env:BONEMET_ISCC`）
  - Windows SDK（提供 `signtool.exe`，用于签名）
- 打包机有网络（pip 下载依赖 / 时间戳签名）

### 2. 生成 release pack 目录

```bash
make release-pack-windows
```

将生成：
- `dist-release/BoneMet-Workstation-<ver>-win-x64/`
- `dist-release/BoneMet-Workstation-<ver>-win-x64.zip`

### 3. 生成 Setup.exe

**Make（推荐）：**

```bash
make windows-setup BONEMET_VERSION=<ver>
# 或从 release pack 一步打完：
make windows-setup-full BONEMET_VERSION=<ver>
# 不含模型（小包）：
make windows-setup-full-no-models BONEMET_VERSION=<ver>
```

**PowerShell：**

```powershell
.\scripts\build-windows-setup.ps1 -Version "<ver>"
.\scripts\build-windows-setup.ps1 -Version "<ver>" -BuildReleasePack -NoModels
.\installer\windows\build_installer.ps1 -Version "<ver>"
.\installer\windows\one_click.ps1 -Version "<ver>" -BuildReleasePack -NoModels
```

**Git Bash：**

```bash
./scripts/build-windows-setup.sh
BONEMET_VERSION=<ver> ./scripts/build-windows-setup.sh --build-release-pack
```

输出：`dist-release/BoneMet-Workstation-<ver>-Setup.exe`

自定义 ISCC（可选）：

```powershell
$env:BONEMET_ISCC = "D:\path\to\ISCC.exe"
make windows-setup BONEMET_VERSION=<ver>
```

### 4. 一键（含 release pack + 可选签名）

```powershell
.\installer\windows\one_click.ps1 -Version "<ver>" -BuildReleasePack
.\installer\windows\one_click.ps1 -Version "<ver>" -PfxPath ".\cert.pfx" -PfxPassword "******"
```

### 5. （可选）用 Nuitka 编译入口

```powershell
cd dist-release\BoneMet-Workstation-<ver>-win-x64
..\..\installer\windows\compile_nuitka.ps1
```

或：`one_click.ps1 -CompileEntrypoints`

### 6. （可选）签名 Setup.exe

```powershell
.\installer\windows\sign_installer.ps1 -Version "<ver>" -PfxPath "path\to\cert.pfx" -PfxPassword "******"
```

### 卸载 / 重新安装

- **Setup.exe**：`unins000.exe` 或 **设置 → 应用**；**再次运行 Setup** 可升级/重装（按注册表 AppId 识别，与目标文件夹是否为空无关），向导默认 **保留 data、不保留模型、不重装 pip**；安装结束自动启动时升级路径只启动、不 pip；可改安装路径，旧目录会被卸载删除，保留项还原到新路径
- **Setup 重装顺序**：备份勾选项 → 删未保留 data/models → **清空旧程序目录** → 写入新包 → 还原 → 清单收尾 → 可选 pip
- **zip 安装**：`卸载.bat` / `重新安装.bat`；「安装并启动」已安装时 **S** 启动 / **R** 重新安装（可选 data/模型/依赖） / **N** 仅重装 pip
- **zip 重装**：须先将新版本 zip 解压覆盖；脚本按选项清理 data/models，并按清单删旧程序文件（逻辑与 Setup 勾选项一致，见 `docs/PACKAGING.md`）
