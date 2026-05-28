"""Stop BoneMet API/worker on Windows (pid files + port cleanup)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from win_port_util import free_port, kill_pid, read_port


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def main() -> int:
    root = _root()
    log_dir = root / "data" / "logs"
    # Default to safe stop: only kill BoneMet processes we can identify.
    aggressive = os.environ.get("BONEMET_AGGRESSIVE_STOP", "0") == "1"
    port = read_port(root, default=int(os.environ.get("BONEMET_PORT", "1012")))

    for name in ("api.pid", "worker.pid"):
        pid = _read_pid(log_dir / name)
        if pid is not None:
            kill_pid(pid)
        (log_dir / name).unlink(missing_ok=True)

    killed = free_port(port, root, aggressive=aggressive)
    if killed:
        print(f"freed port {port}: stopped {killed} process(es)")

    subprocess.run(
        ["taskkill", "/FI", "WINDOWTITLE eq BoneMet Worker*", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        ["taskkill", "/FI", "WINDOWTITLE eq BoneMet API*", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
