"""Exit 0 when BoneMet API /health responds."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _port() -> int:
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from win_port_util import read_port

    return read_port(root)


def main() -> int:
    port = _port()
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return 1
    if data.get("product") == "bonemet-workstation":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
