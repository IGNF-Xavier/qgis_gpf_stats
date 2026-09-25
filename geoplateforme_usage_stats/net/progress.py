"""Progress event vocabulary shared by the catalog and stats workers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 0
    extra: dict = field(default_factory=dict)


ProgressCallback = Callable[[ProgressEvent], None]
CancelCheck = Callable[[], bool]


class OperationCancelled(Exception):
    pass


def noop_progress(_event: ProgressEvent) -> None:
    return None


def never_cancelled() -> bool:
    return False
