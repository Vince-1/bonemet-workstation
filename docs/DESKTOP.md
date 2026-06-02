# 一键安装与启动（无需命令行）

面向医生/科室：**解压安装包 → 双击图标**，不需要打开终端输入命令。

---

## 您收到的安装包怎么用

### 1. 解压

| 系统 | 安装包文件名 |
|------|----------------|
| Linux | `BoneMet-Workstation-*-linux-x64.tar.gz` |
| Windows | `BoneMet-Workstation-*-win-x64.zip` |

解压到任意目录，例如 `/opt/BoneMet` 或 `D:\BoneMet`

路径尽量**不要有中文或空格**。

### 2. 启动（双击即可）

| 系统 | 操作 |
|------|------|
| **Linux** | 进入文件夹，双击 **`安装并启动`**（或 `安装并启动.sh`，选「运行」） |
| **Windows** | 双击 **`安装并启动.bat`** |

- **第一次**会自动安装依赖（需联网约 3～30 分钟），完成后自动打开浏览器。  
- **以后每次**双击（Windows）：**S**=仅启动 · **R**=重新安装（可选保留数据/模型/依赖）· **N**=仅重装 pip。  
- 静默仅启动：`BONEMET_SKIP_INSTALL=1`；强制 pip：`BONEMET_FORCE_INSTALL=1`。  
- 若使用 **Setup.exe** 安装，卸载/升级见 [PACKAGING.md](PACKAGING.md)。  
- Linux 首次成功后，开始菜单会出现 **「BoneMet 骨转移工作站」** 快捷方式。  
- Windows 首次安装成功后：**开始菜单** + **桌面** 会出现带图标的快捷方式（需已放置 `bonemet.ico`，见 [installer/windows/ICON.md](../installer/windows/ICON.md)）。

### 3. 退出

| 系统 | 操作 |
|------|------|
| Linux | 双击 `scripts/stop-bonemet.sh`（若文件管理器允许），或从开始菜单结束进程 |
| Windows | 双击 **`停止BoneMet.bat`** |

### 3.1 卸载 / 重新安装（Windows）

| 操作 | 方式 |
|------|------|
| 卸载 | **设置 → 应用** → **BoneMet 骨转移工作站**；或双击 **`卸载.bat`** |
| 重新安装 | 双击 **`重新安装.bat`**，或在「安装并启动」已安装时选 **R** |
| Setup 升级 | 再次运行新版 **Setup.exe**，向导中勾选保留项（默认保留数据、不保留模型、不重装 pip） |

重新安装 / 卸载时均可选择：**保留病例数据**（默认是）、**保留 AI 模型**（默认否）、**重新安装 Python 依赖 pip**（默认是）。

**重要：** zip 重装前请先将**新版本解压覆盖**到安装目录；重新安装会根据包内清单 `.bonemet_manifest.json` **自动删除新包中已不存在的旧程序文件**（不删 `data\` 里你勾选保留的内容，也不删 `pip` 装入的 `python\Lib\site-packages`，除非勾选重装依赖）。

### 4. 浏览器地址

http://127.0.0.1:1012/（Windows 默认 1012，避免与常见开发端口冲突）

#### 局域网访问（在服务器/开发机上运行）

默认只监听本机（`127.0.0.1`）。如果你希望在 GN2 等服务器上启动后，让同一局域网内的其它电脑访问：

```bash
BONEMET_HOST=0.0.0.0 BONEMET_PUBLIC_HOST=<服务器内网IP> BONEMET_PORT=1012 ./安装并启动.sh
```

然后在其它电脑浏览器打开：

`http://<服务器内网IP>:1012/`

注意：需要服务器防火墙/安全组放行该端口（如 1012）。

### 5. AI 模型

正式安装包**已预置**当前主线模型（检测 ONNX + 骨分割 ONNX），解压即可推理，**无需另行拷贝模型**。

仅当使用不含模型的精简包时，才需手动放入 `data/models/`。

---

## 技术人员：如何制作安装包

在研发机上（需 Node.js、Python 3）：

```bash
cd bonemet-workstation
# 若本机尚未安装模型，先执行一次：
make install-models

make release-pack              # Linux .tar.gz
make release-pack-windows      # Windows .zip
make release-pack-all          # 同时打 Linux + Windows

# 产物示例（默认含 AI 模型，约 600MB+）:
#   dist-release/BoneMet-Workstation-0.2.0-linux-x64.tar.gz
#   dist-release/BoneMet-Workstation-0.2.0-win-x64.zip
```

将对应平台的压缩包交给用户即可。完整流程见 **[PACKAGING.md](PACKAGING.md)**。

**Windows Setup.exe（可选）：**

```bash
make release-pack-windows
make windows-setup BONEMET_VERSION=0.2.0
```

**完全离线安装包**（预置模型 + Python 依赖，体积最大；仅 Linux 预装 venv）：

```bash
WITH_VENV=1 make release-pack
```

**不打模型**（小包，仅程序）：

```bash
BUNDLE_MODELS=0 make release-pack
```

---

## 从源码目录直接双击（研发调试）

仓库根目录已有：

- `安装并启动.sh` / `安装并启动.bat`
- 与安装包内行为相同

开发时仍可用三终端模式：`make api` + `make worker` + `make web`（见 [GETTING_STARTED.md](GETTING_STARTED.md)）。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 双击无反应 | Linux：右键 → 属性 → 允许执行；或终端执行一次 `chmod +x 安装并启动.sh` |
| 首次安装失败 | 检查网络；查看 `data/logs/install.log` |
| 页面打不开 | 确认未重复启动占满端口；先「停止」再启动；查看 `data\logs\api.log`、`install.log` |
| `install.log` 有 pip 报错 | 需联网；安装 [VC++ 运行库](https://aka.ms/vs/17/release/vc_redist.x64.exe)；删除 `.bonemet_installed` 后重试 |
| `api.log` 含 `10048` / 端口占用 | 先双击「停止BoneMet.bat」，再启动；新版会自动改用 8081 等端口，请看 `data\logs\bonemet.port` 里的端口号 |
| 解压后有两层同名文件夹 | 进入内层目录再双击 `安装并启动.bat`，或解压时选「解压到当前文件夹」 |
| models.ok 为 false | 配置 `data/models/` 与 `registry.yaml` |

无 GPU 时自动使用 CPU，速度较慢但可用。
