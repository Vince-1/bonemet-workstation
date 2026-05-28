"""Windows port helpers for BoneMet desktop."""
from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path


def port_file(root: Path) -> Path:
    return root / "data" / "logs" / "bonemet.port"


def read_port(root: Path, default: int = 1012) -> int:
    path = port_file(root)
    if path.is_file():
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pass
    return int(os.environ.get("BONEMET_PORT", str(default)))


def write_port(root: Path, port: int) -> None:
    path = port_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(port), encoding="utf-8")
    os.environ["BONEMET_PORT"] = str(port)


def pids_on_port(port: int) -> set[int]:
    out = subprocess.check_output(
        ["netstat", "-ano"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    pids: set[int] = set()
    needle = f":{port}"
    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return pids


def cmdline(pid: int) -> str:
    try:
        out = subprocess.check_output(
            [
                "wmic",
                "process",
                "where",
                f"ProcessId={pid}",
                "get",
                "CommandLine",
                "/value",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""
    m = re.search(r"CommandLine=(.*)", out, re.DOTALL)
    return (m.group(1).strip() if m else "").lower()


def kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def free_port(port: int, root: Path | None = None, aggressive: bool = False) -> int:
    """Stop listeners on *port*. Returns number of processes killed."""
    root_s = str(root).lower() if root else ""
    markers = (
        "win_launch_api.py",
        "win_launch_worker.py",
        "apps.api.main",
        "apps.worker.main",
        "uvicorn",
        "bonemet",
        root_s,
    )
    killed = 0
    for pid in list(pids_on_port(port)):
        cmd = cmdline(pid)
        if aggressive:
            kill_pid(pid)
            killed += 1
            continue
        if cmd and any(m in cmd for m in markers if m):
            kill_pid(pid)
            killed += 1
    return killed


def find_free_port(start: int, host: str = "127.0.0.1", tries: int = 20) -> int:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"no free TCP port in range {start}-{start + tries - 1} on {host}")
