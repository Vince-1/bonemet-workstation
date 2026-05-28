"""Verify imports after Windows install."""
from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for p in (root / "packages", root):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
site = root / "python" / "Lib" / "site-packages"
if site.is_dir():
    sp = str(site)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import bonemet_core  # noqa: F401
import fastapi  # noqa: F401
import uvicorn  # noqa: F401
from apps.api.main import app  # noqa: F401

print("check passed:", app.title)
