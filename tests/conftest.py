import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages"))


def make_box(cx=0.5, cy=0.5, w=0.1, h=0.1, conf=0.9, cls=0, lesion_id=None, **kw):
    d = {"cx": cx, "cy": cy, "w": w, "h": h, "conf": conf, "cls": cls}
    if lesion_id:
        d["lesion_id"] = lesion_id
    d.update(kw)
    return d
