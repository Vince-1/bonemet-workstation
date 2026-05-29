"""Release file manifest: record packaged files and prune stale program files on reinstall."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MANIFEST_NAME = ".bonemet_manifest.json"

# Only prune under these prefixes (program tree).
MANAGED_PREFIXES = (
    "apps/",
    "packages/",
    "config/",
    "scripts/",
    "deploy/",
    "docs/",
    "schemas/",
    "installer/",
    "python/",
)

# Never prune regardless of manifest.
ALWAYS_SKIP_PREFIXES = (
    "data/",
    ".git/",
    ".venv/",
    "dist-release/",
    "node_modules/",
)

# Root-level program filenames (only these names are considered at repo root).
ROOT_PROGRAM_NAMES = frozenset(
    {
        "requirements.txt",
        "Makefile",
        "安装并启动.bat",
        "安装并启动.sh",
        "停止BoneMet.bat",
        "卸载.bat",
        "重新安装.bat",
        "使用说明.txt",
        MANIFEST_NAME,
        ".bonemet_installed",
        "unins000.exe",
        "unins000.dat",
    }
)

# When walking source tree to build manifest, skip runtime / generated paths.
MANIFEST_SKIP_PREFIXES = (
    "data/cases/",
    "data/incoming/",
    "data/export/",
    "data/logs/",
    ".git/",
    ".venv/",
    "node_modules/",
    "dist-release/",
    "__pycache__/",
    ".pytest_cache/",
)


def _skip_for_manifest(rel_posix: str) -> bool:
    if rel_posix.startswith(MANIFEST_SKIP_PREFIXES):
        return True
    if rel_posix.endswith(".pyc") or rel_posix.endswith(".pyo"):
        return True
    return False


def collect_manifest_files(root: Path) -> list[str]:
    files: list[str] = []
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _skip_for_manifest(rel):
            continue
        files.append(rel)
    files.sort()
    return files


def write_manifest(root: Path, version: str) -> Path:
    root = root.resolve()
    files = collect_manifest_files(root)
    doc = {"version": version, "files": files}
    out = root / MANIFEST_NAME
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote manifest: {out} ({len(files)} files)")
    return out


def load_manifest(root: Path) -> dict:
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"缺少 {MANIFEST_NAME}。请先将新版本安装包解压覆盖到本目录后再重新安装。"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _should_skip_prune(rel_posix: str, opts) -> bool:
    from win_preserve_data import DATA_REL_PATHS, MODELS_REL

    for p in ALWAYS_SKIP_PREFIXES:
        if rel_posix == p.rstrip("/") or rel_posix.startswith(p):
            return True

    if opts.keep_data:
        for rel in DATA_REL_PATHS:
            r = rel.replace("\\", "/")
            if rel_posix == r or rel_posix.startswith(r + "/"):
                return True

    if opts.keep_models:
        m = MODELS_REL.replace("\\", "/")
        if rel_posix == m or rel_posix.startswith(m + "/"):
            return True

    if not opts.reinstall_deps:
        if rel_posix.startswith("python/Lib/site-packages/"):
            return True
        if rel_posix.startswith("python/Scripts/"):
            return True

    return False


def _is_managed(rel_posix: str) -> bool:
    if rel_posix in ROOT_PROGRAM_NAMES:
        return True
    return any(rel_posix.startswith(p) for p in MANAGED_PREFIXES)


def prune_stale_files(root: Path, opts) -> int:
    """Delete program files under managed paths that are not in the current manifest."""
    root = root.resolve()
    doc = load_manifest(root)
    allowed = set(doc.get("files", []))
    if MANIFEST_NAME not in allowed:
        allowed.add(MANIFEST_NAME)

    removed = 0
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME:
            continue
        if not _is_managed(rel):
            continue
        if _should_skip_prune(rel, opts):
            continue
        if rel in allowed:
            continue
        try:
            path.unlink()
            print("removed stale:", rel)
            removed += 1
        except OSError as e:
            print(f"warn: could not remove {rel}: {e}", file=sys.stderr)

    # Remove empty directories in managed trees (bottom-up).
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("data/"):
            continue
        if not any(rel == p.rstrip("/") or rel.startswith(p) for p in MANAGED_PREFIXES):
            continue
        if _should_skip_prune(rel + "/", opts):
            continue
        try:
            path.rmdir()
        except OSError:
            pass

    print(f"prune done: removed {removed} stale file(s); manifest version={doc.get('version', '?')}")
    return removed


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: release_manifest.py write <root> [version] | prune", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "write":
        if len(sys.argv) < 3:
            print("usage: release_manifest.py write <root> [version]", file=sys.stderr)
            return 2
        root = Path(sys.argv[2])
        version = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("BONEMET_VERSION", "0.0.0")
        write_manifest(root, version)
        return 0
    if cmd == "prune":
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "scripts"))
        from win_preserve_data import PreserveOptions

        opts = PreserveOptions.from_env()
        prune_stale_files(root, opts)
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
