"""BoneMet Workstation API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.auth import attach_auth
from apps.api.routes.cases import router as cases_router
from apps.api.routes.ingest import router as ingest_router
from apps.api.routes.pacs import router as pacs_router
from bonemet_core.settings import load_config
from bonemet_core.storage.case_index import ensure_index
from bonemet_core.validate import validation_payload

cfg = load_config()
data_root: Path = cfg["_resolved"]["data_root"]
ensure_index(data_root)
app = FastAPI(title="BoneMet Workstation API", version="0.2.0")
app.state.data_root = data_root
app.state.cfg = cfg

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.get("api", {}).get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

attach_auth(app, cfg)
app.include_router(ingest_router)
app.include_router(cases_router)
app.include_router(pacs_router)


@app.get("/health")
def health():
    models = validation_payload(data_root)
    return {
        "status": "ok" if models["ok"] else "degraded",
        "product": "bonemet-workstation",
        "version": "0.2.0",
        "data_root": str(data_root),
        "models": models,
    }


# SPA last: API routes registered above take precedence over static mount.
from apps.api.static_mount import attach_spa

if not attach_spa(app):
    import logging

    logging.getLogger("bonemet.api").warning(
        "apps/web/dist not found — run: cd apps/web && npm run build  (or make install-desktop)"
    )
