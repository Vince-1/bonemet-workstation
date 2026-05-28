"""Normalize user-entered filesystem paths (Web paste often uses backslashes)."""
from __future__ import annotations

from pathlib import Path


def normalize_ingest_path(raw: str) -> Path:
    s = raw.strip().strip('"').strip("'")
    if not s:
        raise ValueError("路径为空")
    s = s.replace("\\", "/")
    # \wenhao\trains\... → /wenhao/trains/...（粘贴常见）
    if s.startswith("/wenhao/"):
        s = "/home" + s
    elif s.startswith("wenhao/"):
        s = "/home/" + s

    p = Path(s).expanduser()
    if p.is_file() or p.is_dir():
        return p.resolve()

    rel = s.lstrip("/")
    if rel:
        for base in (Path.home(), Path("/home/wenhao")):
            cand = (base / rel).resolve()
            if cand.is_file() or cand.is_dir():
                return cand

    return p
