"""Append-only telemetry export to JSON (list of dicts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_telemetry_json(path: str | Path, rows: list[dict[str, Any]], *, indent: int = 2) -> None:
    """Save a list of timestep records to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=indent)
