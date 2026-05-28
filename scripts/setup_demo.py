#!/usr/bin/env python3
"""Install demo case with placeholder images for local dev."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bonemet_core import queue as queue_mod
from bonemet_core.settings import load_config
from bonemet_core.validate import validate_models

STUDY_UID = "STUDY_DEMO_001"


def make_placeholder(path: Path, label: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        path.write_bytes(b"")
        return
    img = Image.new("L", (512, 1024), color=40)
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), label, fill=220)
    draw.ellipse((180, 300, 280, 380), outline=200, width=3)
    img.save(path)


def main() -> int:
    cfg = load_config()
    data_root = cfg["_resolved"]["data_root"]
    src = ROOT / "schemas" / "examples" / "case_bundle_minimal"
    dest = data_root / "cases" / "case_bundle" / STUDY_UID
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    img_dir = dest / "images"
    img_dir.mkdir(exist_ok=True)
    make_placeholder(img_dir / "front.png", "ANTERIOR")
    make_placeholder(img_dir / "back.png", "POSTERIOR")

    import numpy as np

    from PIL import Image

    def raw(path: Path) -> np.ndarray:
        return np.array(Image.open(path).convert("L"), dtype=np.float32)

    front = raw(img_dir / "front.png")
    back = raw(img_dir / "back.png")
    h, w = max(front.shape[0], back.shape[0]), max(front.shape[1], back.shape[1])

    def pad(img: np.ndarray) -> np.ndarray:
        out = np.zeros((h, w), dtype=np.float32)
        out[: img.shape[0], : img.shape[1]] = img
        return out

    vol = np.stack([pad(back), pad(front)], axis=0)
    from bonemet_core.nifti_io import write_nii_array

    inf = dest / "inference"
    inf.mkdir(parents=True, exist_ok=True)
    write_nii_array(inf / "input_volume.nii.gz", vol, dtype=np.float32)

    meta_path = dest / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["study_uid"] = STUDY_UID
    meta["patient_display_id"] = "DEMO-001"
    meta["status"] = "ingesting"
    meta["pipeline_status"] = "queued"
    meta["rev"] = 0
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mv = validate_models(data_root)
    if mv.ok:
        queue_mod.enqueue_pipeline(data_root, STUDY_UID)
        print("pipeline queued (models OK)")
    else:
        print("demo case created but pipeline NOT queued — install models first:")
        for err in mv.errors:
            print(f"  - {err}")
        print("  bash scripts/install_models.sh && make worker")
    print(f"demo case ready: {dest}")
    print("start: make api && make worker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
