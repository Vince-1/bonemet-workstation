"""Normalized box helpers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Box:
    cls: int = 0
    cx: float = 0.0
    cy: float = 0.0
    w: float = 0.1
    h: float = 0.1
    conf: float = 1.0
    lesion_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("lesion_id") is None:
            d.pop("lesion_id", None)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Box:
        return cls(
            cls=int(raw.get("cls", 0)),
            cx=float(raw["cx"]),
            cy=float(raw["cy"]),
            w=float(raw["w"]),
            h=float(raw["h"]),
            conf=float(raw.get("conf", 1.0)),
            lesion_id=raw.get("lesion_id"),
        )


def boxes_to_dicts(boxes: list[Box]) -> list[dict[str, Any]]:
    return [b.to_dict() for b in boxes]
