from __future__ import annotations

import json
from pathlib import Path


def read_json(path: str | Path) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, obj: dict) -> None:
    p = Path(path)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
