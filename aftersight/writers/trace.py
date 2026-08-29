"""`trace.jsonl`, one event per line, for `jq` and for rebuilding the run.

Append, never truncate: a resumed run's trace continues past earlier attempts.
It is also the source of truth that `outline.md` and `analytics.json` are
regenerated from, so it must survive a crash mid-run.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from aftersight import constants
from aftersight.events.schemas import Event


class TraceWriter:
    def __init__(self, run_dir: Path):
        self.path = run_dir / constants.TRACE_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a")

    def __call__(self, event: Event) -> None:
        self._handle.write(json.dumps(event.to_dict()) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def read_events(run_dir: Path) -> Iterator[Event]:
    path = Path(run_dir) / constants.TRACE_FILE
    if not path.is_file():
        return
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield Event.from_dict(json.loads(line))
