"""Dead Letter Queue — failed events after max retries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from vasini.events.envelope import CloudEvent


@dataclass
class DLQEntry:
    event: CloudEvent
    error: str
    retry_count: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DeadLetterQueue:
    def __init__(self) -> None:
        self.entries: list[DLQEntry] = []

    def add(self, event: CloudEvent, error: str, retry_count: int) -> None:
        self.entries.append(DLQEntry(event=event, error=error, retry_count=retry_count))

    def replay(self, event_id: str) -> CloudEvent | None:
        for i, entry in enumerate(self.entries):
            if entry.event.id == event_id:
                self.entries.pop(i)
                return entry.event
        return None

    @property
    def depth(self) -> int:
        return len(self.entries)
