"""Rasterize bonemet-icon.svg design to bonemet.png + bonemet.ico (Pillow only, no Cairo)."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "installer" / "windows"
WEB_PUBLIC = ROOT / "apps" / "web" / "public"
SIZE = 1024
# Design from bonemet-icon.svg (512 coords × 2)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _gradient_color(t: float) -> tuple[int, int, int, int]:
    # #a5f3fc -> #5eead4 -> #34d399
    if t < 0.5:
        t2 = t / 0.5
        return (
            _lerp(165, 94, t2),
            _lerp(243, 234, t2),
            _lerp(252, 212, t2),
            255,
        )
    t2 = (t - 0.5) / 0.5
    return (
        _lerp(94, 52, t2),
        _lerp(234, 211, t2),
        _lerp(212, 153, t2),
        255,
    )


def _rounded_bar(
    base: Image.Image,
    cx: int,
    cy: int,
    w: int,
    h: int,
    radius: int,
    angle_deg: float,
    fill: tuple[int, int, int, int],
) -> None:
    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=radius, fill=fill)
    if angle_deg:
        layer = layer.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
    ox = cx - layer.width // 2
    oy = cy - layer.height // 2
    base.alpha_composite(layer, (ox, oy))


def render(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 224 / 512), fill=(26, 35, 50, 255))

    s = size / 512
    bars = [
        (256 * s, 144 * s, 76 * s, 52 * s, 26 * s, -6, 0.0),
        (256 * s, 224 * s, 92 * s, 56 * s, 28 * s, 0, 0.35),
        (256 * s, 289 * s, 84 * s, 54 * s, 27 * s, 4, 0.65),
        (256 * s, 356 * s, 68 * s, 48 * s, 24 * s, 8, 1.0),
    ]
    for cx, cy, w, h, r, ang, t in bars:
        _rounded_bar(img, int(cx), int(cy), int(w), int(h), int(r), ang, _gradient_color(t))

    cx, cy = int(256 * s), int(256 * s)
    for ring_r, alpha in ((168 * s, 46), (132 * s, 31)):
        draw.ellipse(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            outline=(103, 232, 249, alpha),
            width=max(2, int(2 * s)),
        )
    return img


def main() -> None:
    img = render()
    png_path = OUT_DIR / "bonemet.png"
    ico_path = OUT_DIR / "bonemet.ico"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(png_path, "PNG")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    WEB_PUBLIC.mkdir(parents=True, exist_ok=True)
    web_png = WEB_PUBLIC / "bonemet.png"
    web_ico = WEB_PUBLIC / "favicon.ico"
    img.save(web_png, "PNG")
    img.save(
        web_ico,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Wrote {png_path} ({png_path.stat().st_size} bytes)")
    print(f"Wrote {ico_path} ({ico_path.stat().st_size} bytes)")
    print(f"Wrote {web_png} (web favicon)")
    print(f"Wrote {web_ico} (web favicon)")


if __name__ == "__main__":
    main()
