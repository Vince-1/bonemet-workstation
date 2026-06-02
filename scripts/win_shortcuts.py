"""Windows start menu / desktop shortcuts with optional bonemet.ico."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from win_uninstall_common import DISPLAY_NAME, START_MENU_FOLDER, app_icon_ico


def _desktop_dir() -> Path | None:
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Environment]::GetFolderPath('Desktop')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    p = (r.stdout or "").strip()
    return Path(p) if p and Path(p).is_dir() else None


def create_shortcut(
    target: Path,
    link: Path,
    description: str,
    icon: Path | None = None,
) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    target_s = str(target.resolve()).replace("'", "''")
    wd_s = str(target.parent.resolve()).replace("'", "''")
    desc_s = description.replace("'", "''")
    lines = [
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);",
        f"$s.TargetPath = '{target_s}';",
        f"$s.WorkingDirectory = '{wd_s}';",
        f"$s.Description = '{desc_s}';",
    ]
    if icon and icon.is_file():
        icon_s = str(icon.resolve()).replace("'", "''")
        lines.append(f"$s.IconLocation = '{icon_s},0';")
    lines.append("$s.Save()")
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "".join(lines)],
        env={**os.environ, "LNK": str(link.resolve())},
        check=False,
    )


def install_shortcuts(root: Path, *, desktop: bool = True) -> None:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return
    icon = app_icon_ico(root)
    menu_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER

    launch = root / "安装并启动.bat"
    if launch.is_file():
        create_shortcut(launch, menu_dir / "启动 BoneMet.lnk", "启动 BoneMet 骨转移工作站", icon)
        if desktop:
            desk = _desktop_dir()
            if desk:
                create_shortcut(launch, desk / "BoneMet 骨转移工作站.lnk", DISPLAY_NAME, icon)

    for bat, label in (
        (root / "停止BoneMet.bat", "停止 BoneMet"),
        (root / "重新安装.bat", "重新安装 BoneMet"),
        (root / "卸载.bat", "卸载 BoneMet"),
    ):
        if bat.is_file():
            create_shortcut(bat, menu_dir / f"{label}.lnk", label, icon)
