"""Append-only audit log for case operations.

Each case bundle gets an `audit.log.ndjson` file with one JSON line per event.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def log_event(
    bundle_dir: Path,
    action: str,
    *,
    detail: dict[str, Any] | None = None,
    user: str = "system",
) -> None:
    """Append a single audit event to the case's audit log."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    log_path = bundle_dir / "audit.log.ndjson"
    event = {
        "ts": _now_iso(),
        "action": action,
        "user": user,
    }
    if detail:
        event["detail"] = detail
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
