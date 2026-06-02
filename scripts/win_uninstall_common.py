"""Shared constants for Windows install / uninstall registration."""
from __future__ import annotations

from pathlib import Path

APP_UNINSTALL_KEY = "B4B0E18E-6E85-4E6E-9A2A-6C8F3A9D4E7B"
DISPLAY_NAME = "BoneMet 骨转移工作站"
PUBLISHER = "BoneMet"
DEFAULT_VERSION = "0.2.0"
START_MENU_FOLDER = "BoneMet 骨转移工作站"
APP_ICON_ICO = "bonemet.ico"
APP_ICON_PNG = "bonemet.png"


def app_icon_ico(root: Path) -> Path | None:
    p = root / APP_ICON_ICO
    return p if p.is_file() else None


def app_icon_png(root: Path) -> Path | None:
    p = root / APP_ICON_PNG
    return p if p.is_file() else None
