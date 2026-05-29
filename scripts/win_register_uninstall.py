"""Register BoneMet in Windows Settings → Apps (portable / zip install only)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from win_uninstall_common import (
    APP_UNINSTALL_KEY,
    DEFAULT_VERSION,
    DISPLAY_NAME,
    PUBLISHER,
    START_MENU_FOLDER,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _version() -> str:
    return os.environ.get("BONEMET_VERSION", DEFAULT_VERSION).strip() or DEFAULT_VERSION


def _programs_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        raise RuntimeError("APPDATA not set")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _shortcut(target: Path, link: Path, description: str) -> None:
    import subprocess

    link.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
        f"$s.TargetPath = '{target}';"
        f"$s.WorkingDirectory = '{target.parent}';"
        f"$s.Description = '{description}';"
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        env={**os.environ, "LNK": str(link)},
        check=False,
    )


def _create_start_menu_shortcuts(root: Path, menu_dir: Path) -> None:
    launch = root / "安装并启动.bat"
    stop = root / "停止BoneMet.bat"
    reinstall = root / "重新安装.bat"
    uninstall = root / "卸载.bat"
    entries = (
        (launch, "启动 BoneMet"),
        (stop, "停止 BoneMet"),
        (reinstall, "重新安装 BoneMet"),
        (uninstall, "卸载 BoneMet"),
    )
    for bat, label in entries:
        if bat.is_file():
            _shortcut(bat, menu_dir / f"{label}.lnk", label)


def register() -> None:
    if sys.platform != "win32":
        print("skip: not Windows")
        return

    root = _root()
    if (root / "unins000.exe").is_file():
        print("skip: Inno Setup install (unins000.exe present)")
        return

    import winreg

    uninstall_bat = root / "scripts" / "uninstall-bonemet.bat"
    if not uninstall_bat.is_file():
        raise FileNotFoundError(uninstall_bat)

    cmd = f'"{uninstall_bat}"'
    version = _version()
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_UNINSTALL_KEY}"

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, DISPLAY_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(root))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, cmd)
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f"{cmd} /SILENT")
        icon = root / "安装并启动.bat"
        if icon.is_file():
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)

    menu_dir = _programs_dir() / START_MENU_FOLDER
    _create_start_menu_shortcuts(root, menu_dir)
    print(f"registered uninstall: {DISPLAY_NAME} ({version})")


if __name__ == "__main__":
    register()
