"""Registry / model file validation — required before pipeline or ingest with run_pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bonemet_core.registry import resolve_bone_models, resolve_detect_model


@dataclass
class ModelValidationResult:
    ok: bool
    errors: list[str]
    detect_path: Path | None
    bone_big_path: Path | None
    bone_axis_path: Path | None
    bone_big_plans_path: Path | None
    bone_axis_plans_path: Path | None


def validate_models(data_root: Path) -> ModelValidationResult:
    errors: list[str] = []
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        errors.append("未安装 onnxruntime（推理必需）: pip install onnxruntime")

    detect = resolve_detect_model(data_root)
    if detect is None:
        errors.append("registry.yaml: active.detect 未配置")
    elif not detect.is_file():
        errors.append(f"检测模型文件不存在: {detect}")

    bone = resolve_bone_models(data_root)
    big = bone.get("bone_big_onnx")
    axis = bone.get("bone_axis_onnx")
    big_plans = bone.get("bone_big_plans")
    axis_plans = bone.get("bone_axis_plans")

    if big is None or axis is None:
        errors.append("registry.yaml: active.bone_seg 未配置 big_path / axis_path")
    else:
        if not big.is_file():
            errors.append(f"骨分割 Big ONNX 不存在: {big}")
        if not axis.is_file():
            errors.append(f"骨分割 Axis ONNX 不存在: {axis}")
    if big_plans is None or axis_plans is None:
        errors.append("registry.yaml: bone_seg 缺少 big_plans_path / axis_plans_path")
    else:
        if not big_plans.is_file():
            errors.append(f"BigPlans.json 不存在: {big_plans}")
        if not axis_plans.is_file():
            errors.append(f"RibPlans.json 不存在: {axis_plans}")

    reg = data_root / "models" / "registry.yaml"
    if not reg.is_file():
        errors.append(
            f"缺少 {reg}；请复制 registry.example.yaml 并运行 scripts/install_models.sh"
        )

    return ModelValidationResult(
        ok=not errors,
        errors=errors,
        detect_path=detect,
        bone_big_path=big,
        bone_axis_path=axis,
        bone_big_plans_path=big_plans,
        bone_axis_plans_path=axis_plans,
    )


def require_models(data_root: Path) -> ModelValidationResult:
    result = validate_models(data_root)
    if not result.ok:
        raise RuntimeError("模型配置不完整，无法启动流水线:\n- " + "\n- ".join(result.errors))
    return result


def validation_payload(data_root: Path) -> dict[str, Any]:
    r = validate_models(data_root)
    return {
        "ok": r.ok,
        "errors": r.errors,
        "detect": str(r.detect_path) if r.detect_path else None,
        "bone_big_onnx": str(r.bone_big_path) if r.bone_big_path else None,
        "bone_axis_onnx": str(r.bone_axis_path) if r.bone_axis_path else None,
    }
