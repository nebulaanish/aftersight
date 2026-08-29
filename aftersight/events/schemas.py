from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Event:
    run_id: str
    seq: int
    attempt: int
    ts: float
    type: str
    name: str | None = None
    parent_seq: int | None = None
    status: str | None = None
    dur_ms: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def anchor(self) -> str:
        """`#0016`. The same string in outline.md, agent.logs and trace.jsonl."""
        return f"#{self.seq:04d}"

    def datetime(self) -> datetime:
        """Local time with an explicit offset. A user correlating a run with their
        own terminal reads a local clock, and the offset keeps it unambiguous."""
        return datetime.fromtimestamp(self.ts).astimezone()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "seq": self.seq,
            "attempt": self.attempt,
            "ts": round(self.ts, 3),
            "iso": self.datetime().isoformat(),
            "type": self.type,
            "name": self.name,
            "parent_seq": self.parent_seq,
            "status": self.status,
            "dur_ms": self.dur_ms,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            run_id=data["run_id"],
            seq=data["seq"],
            attempt=data.get("attempt", 1),
            ts=data["ts"],
            type=data["type"],
            name=data.get("name"),
            parent_seq=data.get("parent_seq"),
            status=data.get("status"),
            dur_ms=data.get("dur_ms"),
            payload=data.get("payload", {}),
        )
