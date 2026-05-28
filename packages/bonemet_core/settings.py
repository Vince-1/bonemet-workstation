"""Load config from BONEMET_CONFIG / default.example.yaml only."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PRODUCT_ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict:
    path = os.environ.get("BONEMET_CONFIG")
    if path and Path(path).is_file():
        cfg_path = Path(path)
    else:
        local = PRODUCT_ROOT / "config" / "local.yaml"
        cfg_path = local if local.is_file() else PRODUCT_ROOT / "config" / "default.example.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    data_root = Path(os.environ.get("BONEMET_DATA_ROOT") or cfg.get("paths", {}).get("data_root", "./data"))
    if not data_root.is_absolute():
        data_root = (PRODUCT_ROOT / data_root).resolve()
    cfg["_resolved"] = {"data_root": data_root, "product_root": PRODUCT_ROOT}
    return cfg
