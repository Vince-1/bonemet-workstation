"""PACS status & control endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from apps.pacs.incoming import incoming_root, list_incoming
from apps.pacs.ingester import process_all_pending, process_one_study

router = APIRouter(prefix="/api/pacs", tags=["pacs"])


@router.get("/status")
def pacs_status(request: Request) -> dict[str, Any]:
    """Return SCP/watcher config, incoming queue depth, and recent items."""
    data_root = request.app.state.data_root
    cfg = request.app.state.cfg
    pacs_cfg = cfg.get("pacs", {})

    items = list_incoming(data_root)
    counts = {"pending": 0, "ingesting": 0, "done": 0, "failed": 0}
    for item in items:
        s = item.get("status", "pending")
        if s in counts:
            counts[s] += 1

    return {
        "scp": {
            "enabled": pacs_cfg.get("scp", {}).get("enabled", False),
            "port": pacs_cfg.get("scp", {}).get("port", 11112),
            "ae_title": pacs_cfg.get("scp", {}).get("ae_title", "BONEMET"),
        },
        "watcher": {
            "enabled": pacs_cfg.get("watcher", {}).get("enabled", False),
            "watch_dir": pacs_cfg.get("watcher", {}).get("watch_dir", ""),
        },
        "incoming": {
            "total": len(items),
            **counts,
            "items": items[-50:],
        },
    }


@router.post("/incoming/{study_uid}/retry")
def retry_study(request: Request, study_uid: str) -> dict[str, Any]:
    """Manually retry ingesting a failed study."""
    data_root = request.app.state.data_root
    sdir = incoming_root(data_root) / study_uid
    if not sdir.is_dir():
        return {"error": f"study {study_uid} not found in incoming"}
    from apps.pacs.incoming import set_status
    set_status(sdir, "pending")
    result = process_one_study(data_root, sdir)
    return result


@router.post("/incoming/process-all")
def process_all(request: Request) -> dict[str, Any]:
    """Trigger processing of all pending incoming studies."""
    data_root = request.app.state.data_root
    results = process_all_pending(data_root)
    return {"processed": len(results), "results": results}
