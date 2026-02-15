"""CloudEvents 1.0 envelope."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CloudEvent:
    specversion: str = "1.0"
    type: str = ""
    source: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    datacontenttype: str = "application/json"
    data: dict = field(default_factory=dict)
    subject: str = ""
    tenant_id: str = ""


def build_event(
    event_type: str,
    source: str,
    data: dict,
    subject: str = "",
    tenant_id: str = "",
) -> CloudEvent:
    return CloudEvent(
        type=event_type,
        source=source,
        data=data,
        subject=subject,
        tenant_id=tenant_id,
    )
