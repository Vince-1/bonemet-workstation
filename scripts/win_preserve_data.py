"""Backup / restore user data & models for Windows reinstall or uninstall."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

# User data (cases, exports, local config)
DATA_REL_PATHS = (
    "data/cases",
    "data/export",
    "data/incoming",
    "data/queue",
    "config/local.yaml",
)

MODELS_REL = "data/models"


@dataclass
class PreserveOptions:
    keep_data: bool = True
    keep_models: bool = False
    # False = 保留已安装的 pip 依赖（默认）；True = 重新执行 pip install
    reinstall_deps: bool = False

    @classmethod
    def from_env(cls) -> PreserveOptions:
        def _flag(name: str, default: bool) -> bool:
            raw = os.environ.get(name, "").strip().lower()
            if raw in ("1", "true", "yes", "on"):
                return True
            if raw in ("0", "false", "no", "off"):
                return False
            return default

        return cls(
            keep_data=_flag("BONEMET_KEEP_DATA", True),
            keep_models=_flag("BONEMET_KEEP_MODELS", False),
            reinstall_deps=_flag("BONEMET_REINSTALL_DEPS", False),
        )


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _rel_paths(opts: PreserveOptions) -> list[str]:
    out: list[str] = []
    if opts.keep_data:
        out.extend(DATA_REL_PATHS)
    if opts.keep_models:
        out.append(MODELS_REL)
    return out


def backup_to_staging(root: Path, opts: PreserveOptions, staging: Path | None = None) -> Path:
    staging = Path(staging or tempfile.mkdtemp(prefix="bonemet-preserve-"))
    staging.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    for rel in _rel_paths(opts):
        src = root / rel
        if not src.exists():
            continue
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        manifest.append(rel)
    (staging / "manifest.json").write_text(
        json.dumps(
            {
                "paths": manifest,
                "keep_data": opts.keep_data,
                "keep_models": opts.keep_models,
                "reinstall_deps": opts.reinstall_deps,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"backed up {len(manifest)} path(s) -> {staging}")
    return staging


def restore_from_staging(staging: Path, root: Path) -> None:
    manifest_path = staging / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rels = manifest.get("paths", [])
    else:
        rels = [p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file() and p.name != "manifest.json"]

    for rel in rels:
        src = staging / rel
        if not src.exists():
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
    print(f"restored from {staging}")


def remove_paths(root: Path, rels: list[str]) -> None:
    for rel in rels:
        p = root / rel
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)


def clear_for_reinstall(root: Path, opts: PreserveOptions) -> Path | None:
    """Remove models/data per options; return staging dir if backup was created."""
    staging: Path | None = None
    if opts.keep_data or opts.keep_models:
        staging = backup_to_staging(root, opts)

    if not opts.keep_models and (root / MODELS_REL).exists():
        shutil.rmtree(root / MODELS_REL, ignore_errors=True)
        print("removed:", root / MODELS_REL)

    if not opts.keep_data:
        remove_paths(root, list(DATA_REL_PATHS))
        print("removed user data under data/ and config/local.yaml")

    marker = root / ".bonemet_installed"
    if opts.reinstall_deps:
        if marker.is_file():
            marker.unlink()
            print("removed install marker (.bonemet_installed) — will reinstall pip deps")
        py_tree = root / "python"
        if py_tree.exists():
            shutil.rmtree(py_tree, ignore_errors=True)
            print("removed:", py_tree, "(will restore from new package + pip)")
    else:
        print("keeping pip dependencies (.bonemet_installed unchanged)")

    return staging


def prune_program_keep_user_content(root: Path, opts: PreserveOptions) -> None:
    """Remove program tree but leave preserved user dirs in place (uninstall)."""
    staging = backup_to_staging(root, opts) if (opts.keep_data or opts.keep_models) else None

    program_dirs = (
        "apps",
        "packages",
        "python",
        "config",
        "deploy",
        "docs",
        "schemas",
        "installer",
        "dist-release",
    )
    program_files = (
        "requirements.txt",
        "Makefile",
        "安装并启动.bat",
        "停止BoneMet.bat",
        "卸载.bat",
        "重新安装.bat",
        ".bonemet_installed",
        "unins000.exe",
        "unins000.dat",
    )
    for name in program_dirs:
        p = root / name
        if p.exists():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    for name in program_files:
        p = root / name
        if p.is_file():
            p.unlink(missing_ok=True)

    if not opts.keep_models and (root / MODELS_REL).exists():
        shutil.rmtree(root / MODELS_REL, ignore_errors=True)
    if not opts.keep_data:
        remove_paths(root, list(DATA_REL_PATHS))

    if staging:
        restore_from_staging(staging, root)
        shutil.rmtree(staging, ignore_errors=True)


def prompt_preserve_options(title: str) -> PreserveOptions:
    import ctypes

    MB_YESNO = 0x04
    MB_DEFBUTTON1 = 0x00
    MB_DEFBUTTON2 = 0x100
    IDYES = 6

    r1 = ctypes.windll.user32.MessageBoxW(
        0,
        "是否保留病例与配置数据？\n\n包括：data\\cases、data\\export、config\\local.yaml 等。",
        title,
        MB_YESNO | MB_DEFBUTTON1,
    )
    keep_data = r1 == IDYES

    r2 = ctypes.windll.user32.MessageBoxW(
        0,
        "是否保留 AI 模型文件？\n\n即 data\\models 目录（ONNX 等，体积较大）。",
        title,
        MB_YESNO | MB_DEFBUTTON2,
    )
    keep_models = r2 == IDYES

    r3 = ctypes.windll.user32.MessageBoxW(
        0,
        "是否重新安装 Python 依赖 (pip)？\n\n选「否」保留当前已装依赖（推荐，较快）。\n选「是」将重新下载安装 requirements（约 10～30 分钟，需联网）。",
        title,
        MB_YESNO | MB_DEFBUTTON2,
    )
    reinstall_deps = r3 == IDYES

    return PreserveOptions(keep_data=keep_data, keep_models=keep_models, reinstall_deps=reinstall_deps)
