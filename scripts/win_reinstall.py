"""Prepare in-place reinstall: preserve data/models/deps per options, then re-run install-and-run."""
from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path

from release_manifest import prune_stale_files
from win_preserve_data import PreserveOptions, clear_for_reinstall, prompt_preserve_options
from win_uninstall import _stop_services
from win_uninstall_common import DISPLAY_NAME

_SKIP_DEPS_FLAG = ".bonemet_reinstall_skip_deps"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_silent(argv: list[str]) -> bool:
    return any(a.upper() in ("/SILENT", "-SILENT", "--SILENT") for a in argv)


def _write_skip_deps_flag(root: Path, skip: bool) -> None:
    flag = root / _SKIP_DEPS_FLAG
    if skip:
        flag.write_text("1", encoding="utf-8")
    elif flag.is_file():
        flag.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="BoneMet Windows reinstall prep")
    parser.add_argument("--prepare", action="store_true", help="Clear models/data per options (default action)")
    parser.add_argument("--run-install", action="store_true", help="After --prepare, run install-and-run.bat")
    parser.add_argument("--silent", action="store_true")
    args, unknown = parser.parse_known_args()
    silent = args.silent or _is_silent(unknown) or _is_silent(sys.argv[1:])

    root = _root()
    if (root / "unins000.exe").is_file() and not os.environ.get("BONEMET_ALLOW_INPLACE_REINSTALL"):
        msg = (
            "当前为 Setup.exe 安装。\n\n"
            "请重新运行新版本的 Setup.exe 完成升级；安装向导中可选择是否保留数据/模型/依赖。\n\n"
            "若仅需重装 Python 依赖，请用「安装并启动.bat」并选择 N。"
        )
        if not silent:
            ctypes.windll.user32.MessageBoxW(0, msg, DISPLAY_NAME, 0x40)
        print(msg)
        return 1

    env_override = (
        silent
        or os.environ.get("BONEMET_KEEP_DATA")
        or os.environ.get("BONEMET_KEEP_MODELS")
        or os.environ.get("BONEMET_REINSTALL_DEPS")
    )
    if env_override:
        opts = PreserveOptions.from_env()
    elif not silent:
        opts = prompt_preserve_options(f"{DISPLAY_NAME} 重新安装")
    else:
        opts = PreserveOptions()

    print(
        "reinstall options:",
        f"keep_data={opts.keep_data}",
        f"keep_models={opts.keep_models}",
        f"reinstall_deps={opts.reinstall_deps}",
    )
    _stop_services(root)
    clear_for_reinstall(root, opts)
    try:
        n_removed = prune_stale_files(root, opts)
    except FileNotFoundError as e:
        if not silent:
            ctypes.windll.user32.MessageBoxW(0, str(e), DISPLAY_NAME, 0x30)
        print(e, file=sys.stderr)
        return 1
    _write_skip_deps_flag(root, skip=not opts.reinstall_deps)

    if not silent:
        deps_hint = "将重新安装 Python 依赖 (pip)。" if opts.reinstall_deps else "将保留已安装的 Python 依赖。"
        ctypes.windll.user32.MessageBoxW(
            0,
            "已准备好重新安装。\n\n"
            f"{deps_hint}\n"
            f"已清理新包中不存在的旧程序文件 {n_removed} 个。\n"
            "请确保已先将新版本 zip 解压覆盖到本目录。",
            DISPLAY_NAME,
            0x40,
        )

    if args.run_install:
        bat = root / "scripts" / "install-and-run.bat"
        if not bat.is_file():
            print("missing", bat, file=sys.stderr)
            return 1
        env = os.environ.copy()
        if opts.reinstall_deps:
            env["BONEMET_FORCE_INSTALL"] = "1"
            env.pop("BONEMET_SKIP_INSTALL", None)
        else:
            env["BONEMET_SKIP_INSTALL"] = "1"
            env.pop("BONEMET_FORCE_INSTALL", None)
        return subprocess.call(["cmd", "/c", str(bat)], cwd=root, env=env)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
