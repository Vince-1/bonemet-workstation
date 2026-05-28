"""Optional HTTP Basic Auth (Phase 2). Enable in config/local.yaml auth.basic_enabled."""
from __future__ import annotations

import base64
import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool, user: str, password: str):
        super().__init__(app)
        self.enabled = enabled
        self.user = user
        self.password = password

    async def dispatch(self, request: Request, call_next: Callable):
        if not self.enabled or request.url.path in ("/health",):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            u, _, p = decoded.partition(":")
        except Exception:
            return Response(status_code=401)
        if u != self.user or p != self.password:
            return Response(status_code=401)
        return await call_next(request)


def attach_auth(app, cfg: dict) -> None:
    auth_cfg = cfg.get("auth") or {}
    if not auth_cfg.get("basic_enabled"):
        return
    user = os.environ.get("BONEMET_BASIC_USER") or auth_cfg.get("basic_user") or "clinic"
    password = os.environ.get("BONEMET_BASIC_PASSWORD") or auth_cfg.get("basic_password") or "change-me"
    app.add_middleware(BasicAuthMiddleware, enabled=True, user=user, password=password)
