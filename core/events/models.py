"""Structured events for DIL feedback (coaching, time loss, setup hints)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    TIME_LOSS = "TIME_LOSS"
    COACHING = "COACHING"
    SETUP_HINT = "SETUP_HINT"


@dataclass(frozen=True, slots=True)
class DILEvent:
    kind: EventKind
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
