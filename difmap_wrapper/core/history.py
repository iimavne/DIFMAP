from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .commands import DifmapCommand


class CommandHistory:
    def __init__(self) -> None:
        self._items: list[DifmapCommand] = []

    def add(self, cmd: DifmapCommand) -> None:
        self._items.append(cmd)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def to_dicts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cmd in self._items:
            payload = asdict(cmd)
            payload["__type__"] = type(cmd).__name__
            out.append(payload)
        return out
