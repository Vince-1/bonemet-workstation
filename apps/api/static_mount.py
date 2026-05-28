"""Serve built SPA from apps/web/dist (single-port desktop / production mode)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("bonemet.api")

PRODUCT_ROOT = Path(__file__).resolve().parents[2]


def resolve_web_dist() -> Path | None:
    """Find apps/web/dist (Windows cwd / env may differ from __file__ layout)."""
    env_root = os.environ.get("BONEMET_PRODUCT_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root) / "apps" / "web" / "dist")
    candidates.extend(
        [
            PRODUCT_ROOT / "apps" / "web" / "dist",
            Path.cwd() / "apps" / "web" / "dist",
        ]
    )
    seen: set[Path] = set()
    for raw in candidates:
        dist = raw.resolve()
        if dist in seen:
            continue
        seen.add(dist)
        if (dist / "index.html").is_file():
            return dist
    return None


def attach_spa(app: FastAPI) -> bool:
    """Serve frontend at /. Returns True if dist was found."""
    dist = resolve_web_dist()
    if dist is None:
        logger.warning(
            "SPA not found (checked PRODUCT_ROOT=%s, cwd=%s)",
            PRODUCT_ROOT,
            Path.cwd(),
        )
        return False

    index_path = dist / "index.html"
    assets_dir = dist / "assets"
    logger.info("Serving SPA from %s", dist)

    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="spa-assets",
        )

    @app.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str) -> FileResponse:
        if spa_path.startswith("api/") or spa_path in (
            "health",
            "docs",
            "redoc",
            "openapi.json",
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        target = dist / spa_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(index_path)

    return True
