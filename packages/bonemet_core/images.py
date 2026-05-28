from __future__ import annotations

from pathlib import Path


def image_path(bundle: Path, view: str) -> Path | None:
    for ext in (".webp", ".png", ".jpg"):
        p = bundle / "images" / f"{view}{ext}"
        if p.is_file():
            return p
    return None
