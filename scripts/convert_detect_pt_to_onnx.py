"""Convert Ultralytics YOLO .pt to an ONNX model for bonemet-workstation.

This script is intended for *packaging time* (developer machine / CI) only.
Runtime for bonemet-workstation is ONNXRuntime-only and does NOT require torch/ultralytics.

Output: data/models/detect/v1/model.onnx (with NMS when supported by exporter)
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", required=True, help="Path to best.pt")
    ap.add_argument(
        "--out",
        default="data/models/detect/v1/model.onnx",
        help="Output ONNX path (default: data/models/detect/v1/model.onnx)",
    )
    ap.add_argument("--imgsz", type=int, default=1280, help="Export image size")
    ap.add_argument("--opset", type=int, default=12, help="ONNX opset version")
    ap.add_argument(
        "--nms",
        action="store_true",
        default=True,
        help="Export ONNX with NMS if supported (default: true)",
    )
    ap.add_argument(
        "--no-nms",
        action="store_false",
        dest="nms",
        help="Disable NMS export (not recommended for workstation)",
    )
    args = ap.parse_args()

    pt = Path(args.pt).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not pt.is_file():
        raise SystemExit(f"pt not found: {pt}")

    # Import ultralytics lazily to keep workstation runtime deps clean.
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "ultralytics not installed (export-time dependency).\n"
            "Install in your build env:\n"
            "  pip install ultralytics\n"
            "Then re-run this script.\n"
            f"Original error: {e}"
        )

    model = YOLO(str(pt))
    export_dir = Path(model.export(  # type: ignore[attr-defined]
        format="onnx",
        imgsz=int(args.imgsz),
        opset=int(args.opset),
        simplify=True,
        nms=bool(args.nms),
    )).resolve()

    # Ultralytics returns a path (usually .../best.onnx). Normalize to requested out path.
    exported = export_dir if export_dir.suffix.lower() == ".onnx" else None
    if exported is None or not exported.is_file():
        # try common locations: alongside pt, or model.export prints path string
        cand = list(pt.parent.glob("*.onnx"))
        exported = cand[0] if cand else None
    if exported is None or not exported.is_file():
        raise SystemExit("export succeeded but could not locate .onnx output")

    shutil.copy2(exported, out)
    print(f"OK: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

