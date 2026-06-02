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
    app_icon_ico,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _version() -> str:
    return os.environ.get("BONEMET_VERSION", DEFAULT_VERSION).strip() or DEFAULT_VERSION


def register() -> None:
    if sys.platform != "win32":
        print("skip: not Windows")
        return

    root = _root()
    if (root / "unins000.exe").is_file():
        print("skip: Inno Setup install (unins000.exe present)")
        return

    scripts_dir = root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from win_shortcuts import install_shortcuts

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
        ico = app_icon_ico(root)
        if ico:
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(ico))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)

    install_shortcuts(root, desktop=True)
    print(f"registered uninstall: {DISPLAY_NAME} ({version})")


if __name__ == "__main__":
    register()
