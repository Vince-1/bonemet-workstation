"""Ensure data/models/registry.yaml and model files exist (Windows install / repair)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _bootstrap(product_root: Path) -> None:
    for p in (product_root / "packages", product_root):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    site = product_root / "python" / "Lib" / "site-packages"
    if site.is_dir() and str(site) not in sys.path:
        sys.path.insert(0, str(site))


def _resolve_data_root(product_root: Path) -> Path:
    import os

    raw = os.environ.get("BONEMET_DATA_ROOT")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (product_root / p).resolve()
    from bonemet_core.settings import load_config

    cfg = load_config()
    return Path(cfg["_resolved"]["data_root"])


def _registry_needs_bootstrap(data_root: Path) -> bool:
    from bonemet_core.registry import load_registry

    reg = data_root / "models" / "registry.yaml"
    if not reg.is_file():
        return True
    doc = load_registry(data_root)
    active = doc.get("active") or {}
    models = doc.get("models") or {}
    det = active.get("detect")
    bone = active.get("bone_seg")
    if not det or not bone or det not in models or bone not in models:
        return True
    return False


def ensure_models(
    data_root: Path,
    product_root: Path,
    *,
    repair_registry: bool = False,
) -> tuple[bool, list[str]]:
    messages: list[str] = []
    models_dir = data_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    reg = models_dir / "registry.yaml"
    example = models_dir / "registry.example.yaml"
    if not example.is_file():
        alt = product_root / "data" / "models" / "registry.example.yaml"
        if alt.is_file():
            example = alt

    if repair_registry and _registry_needs_bootstrap(data_root):
        if example.is_file():
            shutil.copy2(example, reg)
            messages.append(f"已写入 registry.yaml ← {example}")
        else:
            messages.append("缺少 registry.example.yaml，无法自动修复配置")

    from bonemet_core.validate import validate_models

    result = validate_models(data_root)
    if not result.ok:
        missing_reg = _registry_needs_bootstrap(data_root)
        if missing_reg:
            messages.append(
                f"配置无效: {reg}\n"
                "  → 运行「修复模型配置.bat」或从安装包复制整个 data\\models 文件夹"
            )
        else:
            messages.append(f"模型目录: {models_dir}")
            for err in result.errors:
                if "registry.yaml" in err and "未配置" in err:
                    continue
                messages.append(f"  - {err}")
            if any("不存在" in e for e in result.errors):
                messages.append(
                    "  → 将 dist-release\\...\\data\\models\\ 整夹复制到安装目录的 data\\models\\"
                )
    return result.ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Check / repair BoneMet model registry")
    parser.add_argument(
        "--repair-registry",
        action="store_true",
        help="Copy registry.example.yaml → registry.yaml if missing or invalid",
    )
    args = parser.parse_args()
    product_root = Path(__file__).resolve().parents[1]
    _bootstrap(product_root)
    data_root = _resolve_data_root(product_root)
    ok, messages = ensure_models(
        data_root, product_root, repair_registry=args.repair_registry
    )
    print(f"data_root: {data_root}")
    for m in messages:
        print(m)
    if ok:
        print("models: OK")
        return 0
    print("models: FAILED")
    if not args.repair_registry:
        print("提示: 运行 scripts\\ensure_models.py --repair-registry 或「修复模型配置.bat」")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
