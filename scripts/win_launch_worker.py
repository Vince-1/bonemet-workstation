"""Windows launcher: fix sys.path then run worker."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> Path:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    for p in (root / "packages", root):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    site = root / "python" / "Lib" / "site-packages"
    if site.is_dir():
        sp = str(site)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    os.environ.setdefault("BONEMET_DATA_ROOT", str(root / "data"))
    os.environ["BONEMET_PRODUCT_ROOT"] = str(root)
    return root


def _write_pid(root: Path) -> None:
    log_dir = root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "worker.pid").write_text(str(os.getpid()), encoding="utf-8")


def _load_ensure_models(root: Path):
    import importlib.util

    path = root / "scripts" / "ensure_models.py"
    spec = importlib.util.spec_from_file_location("bonemet_ensure_models", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    root = _bootstrap()
    _write_pid(root)
    ensure_mod = _load_ensure_models(root)
    ok, msgs = ensure_mod.ensure_models(root / "data", root, repair_registry=True)
    if not ok:
        log = root / "data" / "logs" / "worker.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write("models not ready:\n")
            for m in msgs:
                f.write(m + "\n")
            f.write("Run 修复模型配置.bat or copy data\\models from installer.\n")
    from apps.worker.main import main as worker_main

    worker_main()


if __name__ == "__main__":
    main()
