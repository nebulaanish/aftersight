"""Sequence allocation and fan-out to the writers.

`emit()` is thread-safe: concurrent agents get unique, contiguous sequence
numbers. Sequence numbers continue across a resume, which is why `start_seq`
exists.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from aftersight.events.schemas import Event
from aftersight.utils import log_error, redact


class EventSink:
    def __init__(self, run_id: str, attempt: int = 1, *, start_seq: int = 0,
                 redact_payloads: bool = True):
        self.run_id = run_id
        self.attempt = attempt
        self._seq = start_seq
        self._redact = redact_payloads
        self._writers: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def add_writer(self, writer: Callable[[Event], None]) -> None:
        self._writers.append(writer)

    @property
    def last_seq(self) -> int:
        return self._seq

    def emit(self, type: str, name: str | None = None, *, parent_seq: int | None = None,
             status: str | None = None, dur_ms: int | None = None,
             ts: float | None = None, **payload: Any) -> Event:
        with self._lock:
            self._seq += 1
            event = Event(
                run_id=self.run_id,
                seq=self._seq,
                attempt=self.attempt,
                ts=time.time() if ts is None else ts,
                type=type,
                name=name,
                parent_seq=parent_seq,
                status=status,
                dur_ms=dur_ms,
                payload=redact(payload) if self._redact else payload,
            )
            for write in self._writers:
                try:
                    write(event)
                except Exception as exc:  # noqa: BLE001 (never break the host app)
                    log_error(f"writer {write!r} failed on {event.anchor}: {exc}")
        return event
