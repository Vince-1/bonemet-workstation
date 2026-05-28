"""Windows launcher: fix sys.path then run uvicorn."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> Path:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
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
    (log_dir / "api.pid").write_text(str(os.getpid()), encoding="utf-8")


def main() -> None:
    root = _bootstrap()
    _write_pid(root)

    from win_port_util import find_free_port, write_port

    import uvicorn

    host = "127.0.0.1"
    base = int(os.environ.get("BONEMET_PORT", "1012"))
    # IMPORTANT: never kill other programs bound to the port.
    # If the requested port is busy, just pick the next free one.
    port = find_free_port(base, host=host)
    if port != base:
        print(f"NOTE: port {base} busy, using {port} instead", flush=True)
    write_port(root, port)

    uvicorn.run(
        "apps.api.main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
