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


def main() -> None:
    root = _bootstrap()
    _write_pid(root)
    from apps.worker.main import main as worker_main

    worker_main()


if __name__ == "__main__":
    main()
