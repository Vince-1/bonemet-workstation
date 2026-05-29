"""Uninstall BoneMet (portable / zip). Inno Setup uses unins000.exe instead."""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from win_preserve_data import PreserveOptions, prompt_preserve_options, prune_program_keep_user_content
from win_uninstall_common import APP_UNINSTALL_KEY, DISPLAY_NAME, START_MENU_FOLDER


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_silent(argv: list[str]) -> bool:
    return any(a.upper() in ("/SILENT", "-SILENT", "--SILENT") for a in argv)


def _stop_services(root: Path) -> None:
    py = root / "python" / "python.exe"
    if not py.is_file():
        py = shutil.which("python") or "python"
    script = root / "scripts" / "win_stop_services.py"
    if script.is_file():
        subprocess.run([str(py), str(script)], cwd=root, check=False)


def _unregister() -> None:
    if sys.platform != "win32":
        return
    import winreg

    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_UNINSTALL_KEY}"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        print("removed Programs list entry")
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"warn: could not remove registry key: {e}", file=sys.stderr)


def _remove_start_menu() -> None:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return
    menu_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER
    if menu_dir.is_dir():
        shutil.rmtree(menu_dir, ignore_errors=True)
        print(f"removed start menu: {menu_dir}")


def _confirm_remove_program() -> bool:
    text = (
        "是否删除程序文件？\n\n"
        "选「是」：按上一步选择保留/删除 数据 与 模型，并移除程序。\n"
        "选「否」：仅停止服务并取消「应用和功能」登记，文件夹保留。"
    )
    MB_YESNO = 0x04
    IDYES = 6
    r = ctypes.windll.user32.MessageBoxW(0, text, f"{DISPLAY_NAME} 卸载", MB_YESNO | 0x30)
    return r == IDYES


def main() -> int:
    parser = argparse.ArgumentParser(description="Uninstall BoneMet Workstation")
    parser.add_argument("--silent", action="store_true", help="No UI; unregister only, keep all files")
    args, unknown = parser.parse_known_args()
    silent = args.silent or _is_silent(unknown) or _is_silent(sys.argv[1:])

    root = _root()
    if (root / "unins000.exe").is_file():
        exe = root / "unins000.exe"
        print(f"This install was created with Setup.exe. Run: {exe}")
        if not silent:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"请使用安装目录中的卸载程序：\n\n{exe}\n\n"
                "或在「设置 → 应用」中找到本程序并卸载。\n"
                "重新安装请再次运行 Setup.exe，并在向导中选择是否保留数据/模型。",
                DISPLAY_NAME,
                0x40,
            )
        return 1

    print(f"uninstalling {DISPLAY_NAME} from {root}")
    _stop_services(root)

    if silent:
        opts = PreserveOptions(keep_data=True, keep_models=True)
        remove_program = False
    else:
        opts = prompt_preserve_options(f"{DISPLAY_NAME} 卸载")
        remove_program = _confirm_remove_program()

    _remove_start_menu()
    _unregister()

    if remove_program:
        prune_program_keep_user_content(root, opts)
        summary = (
            f"程序已移除。\n保留数据: {'是' if opts.keep_data else '否'}\n"
            f"保留模型: {'是' if opts.keep_models else '否'}\n\n{root}"
        )
        print(summary.replace("\n", " "))
        if not silent:
            ctypes.windll.user32.MessageBoxW(0, summary, DISPLAY_NAME, 0x40)
    else:
        print("install folder kept:", root)
        if not silent:
            ctypes.windll.user32.MessageBoxW(
                0,
                "已从「应用和功能」移除登记。\n程序与数据文件仍保留在安装目录。",
                DISPLAY_NAME,
                0x40,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
