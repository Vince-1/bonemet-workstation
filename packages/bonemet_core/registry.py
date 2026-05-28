from __future__ import annotations

from pathlib import Path
from typing import Any


def load_registry(data_root: Path) -> dict[str, Any]:
    import yaml

    reg = data_root / "models" / "registry.yaml"
    if not reg.is_file():
        return {}
    doc = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
    return doc


def _expand(path_tpl: str, data_root: Path) -> Path | None:
    if not path_tpl:
        return None
    return Path(path_tpl.replace("{data_root}", str(data_root)))


def resolve_detect_model(data_root: Path) -> Path | None:
    doc = load_registry(data_root)
    active = (doc.get("active") or {}).get("detect")
    models = doc.get("models") or {}
    if not active or active not in models:
        return None
    return _expand(str(models[active].get("path", "")), data_root)


def resolve_bone_models(data_root: Path) -> dict[str, Path | None]:
    doc = load_registry(data_root)
    active = (doc.get("active") or {}).get("bone_seg")
    models = doc.get("models") or {}
    if not active or active not in models:
        return {
            "bone_big_onnx": None,
            "bone_axis_onnx": None,
            "bone_big_plans": None,
            "bone_axis_plans": None,
        }
    entry = models[active]
    return {
        "bone_big_onnx": _expand(str(entry.get("big_path", "")), data_root),
        "bone_axis_onnx": _expand(str(entry.get("axis_path", "")), data_root),
        "bone_big_plans": _expand(str(entry.get("big_plans_path", "")), data_root),
        "bone_axis_plans": _expand(str(entry.get("axis_plans_path", "")), data_root),
    }
