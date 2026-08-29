"""A run: one session's folder, and its lifecycle across attempts.

A resumed session appends into the folder it used before, under a new attempt
banner, with sequence numbers continuing where they stopped. An attempt that
died without `run.end` leaves a crash marker for the next one to write.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from aftersight import constants
from aftersight.config import Config
from aftersight.constants import EventType
from aftersight.events.sink import EventSink
from aftersight.run import store
from aftersight.utils import announce, log_error
from aftersight.writers import analytics, outline
from aftersight.writers.blobs import BlobWriter
from aftersight.writers.trace import TraceWriter, read_events
from aftersight.writers.transcript import TranscriptWriter, attempt_banner, crash_marker


def _git() -> dict[str, Any]:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=2)
        if out.returncode:
            return {}
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                capture_output=True, text=True, timeout=2)
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                               text=True, timeout=2)
        return {"sha": out.stdout.strip(), "branch": branch.stdout.strip(),
                "dirty": bool(dirty.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        return {}


class Run:
    def __init__(self, config: Config, session_id: str | None = None,
                 tags: tuple[str, ...] = (), **meta: Any):
        self.config = config
        self.session_id = session_id
        self.root = store.ensure_root(config.root)
        self.finalized = False
        self._started = time.time()

        resumed = store.resolve_session(self.root, session_id) if session_id else None
        previous = list(read_events(resumed)) if resumed else []
        self.dir = resumed or (store.runs_dir(self.root) /
                               f"{datetime.now():{constants.RUN_ID_TIME_FORMAT}}_"
                               f"{uuid.uuid4().hex[:constants.RUN_ID_SUFFIX_LEN]}")
        self.run_id = self.dir.name
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / constants.ARTIFACTS_DIR).mkdir(exist_ok=True)

        self.attempt = (previous[-1].attempt + 1) if previous else 1
        resume_seq = previous[-1].seq if previous else 0
        crashed = bool(previous) and previous[-1].type != EventType.RUN_END

        self.sink = EventSink(self.run_id, self.attempt, start_seq=resume_seq,
                              redact_payloads=config.redact)
        self._transcript = TranscriptWriter(
            self.dir,
            attempt_banner(self.attempt, datetime.now(), os.getpid(), resume_seq),
            crash_marker(previous[-1].attempt, previous[-1].ts) if crashed else None)
        self._trace = TraceWriter(self.dir)
        self.sink.add_writer(BlobWriter(self.dir, config.blob_max_bytes,
                                        config.blob_preview_lines))
        self.sink.add_writer(self._transcript)
        self.sink.add_writer(self._trace)

        self._write_meta(tags, meta)
        store.point(self.root / constants.LATEST_LINK, self.dir)
        if session_id:
            store.point(self.root / constants.SESSIONS_DIR / session_id, self.dir)

        if self.attempt == 1:
            self.sink.emit(EventType.RUN_START, status="ok", session_id=session_id,
                           **{k: v for k, v in meta.items() if v is not None})
        else:
            self.sink.emit(EventType.RUN_RESUME, status="ok", attempt=self.attempt,
                           resume_seq=resume_seq,
                           reason="crashed" if crashed else "resumed")
        if not config.quiet:
            announce(f"recording to {self.dir}{'' if self.attempt == 1 else f' (attempt {self.attempt})'}")

    def _write_meta(self, tags, meta) -> None:
        existing = store.read_meta(self.dir)
        attempts = existing.get("attempts", [])
        attempts.append({"n": self.attempt, "pid": os.getpid(),
                         "started_at": datetime.now().astimezone().isoformat(),
                         "ended_at": None, "outcome": "running"})
        store.write_meta(self.dir, {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "created_at": existing.get("created_at",
                                       datetime.now().astimezone().isoformat()),
            "python": platform.python_version(),
            "platform": sys.platform,
            "cwd": os.getcwd(),
            "argv": sys.argv,
            "git": existing.get("git") or _git(),
            "tags": list(tags) or existing.get("tags", []),
            **{k: v for k, v in meta.items() if v is not None},
            "attempts": attempts,
        })

    @property
    def artifacts(self) -> Path:
        return self.dir / constants.ARTIFACTS_DIR

    def finalize(self, status: str | None = None) -> dict:
        """`status=None` derives the outcome from whether anything errored, which
        is what the atexit path needs."""
        if self.finalized:
            return {}
        self.finalized = True
        try:
            summary = analytics.summarise(list(read_events(self.dir)))
            if status is None:
                status = "failed" if summary.get("errors") else "ok"
            self.sink.emit(EventType.RUN_END, status=status,
                           dur_ms=int(summary.get("active_sec", 0) * 1000),
                           cost_usd=summary.get("cost", {}).get("cost_usd", 0),
                           llm_calls=summary.get("llm_calls", 0),
                           tool_calls=summary.get("tool_calls", 0),
                           errors=len(summary.get("errors", [])))
            summary = analytics.write(self.dir)
            outline.write(self.dir, summary)
            store.update_index(self.root, summary)
            meta = store.read_meta(self.dir)
            if meta.get("attempts"):
                meta["attempts"][-1].update(
                    ended_at=datetime.now().astimezone().isoformat(),
                    outcome=status, last_seq=self.sink.last_seq)
                store.write_meta(self.dir, meta)
            store.prune(self.root, self.config.keep_runs)
            return summary
        except Exception as exc:  # noqa: BLE001 (never break the host app on the way out)
            log_error(f"finalize failed: {exc}")
            return {}
        finally:
            self._transcript.close()
            self._trace.close()

    def __enter__(self) -> "Run":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None and not getattr(exc, "_aftersight_logged", False):
            self.sink.emit(EventType.ERROR, type(exc).__name__,
                           status="error", error_type=type(exc).__name__, error=str(exc))
        self.finalize("failed" if exc is not None else "ok")
        return False
