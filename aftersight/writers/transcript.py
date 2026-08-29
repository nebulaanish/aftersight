"""`agent.logs`, the transcript a coding agent reads.

Every event opens with a zero-padded `#seq`, the same anchor used by
`outline.md` and `trace.jsonl`. Fixed columns keep the stream scannable and keep
`rg` patterns clean. Column 3 is the delta from the previous event, not a
duration: scanning it finds slow steps with no tooling at all.

Nothing here truncates. A payload too large to inline was already moved to
`blobs/` by `BlobWriter`, and the frame says exactly where it went.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aftersight import constants
from aftersight.constants import EventType
from aftersight.events.schemas import Event
from aftersight.utils import size

def attempt_banner(attempt: int, started: datetime, pid: int, resume_seq: int) -> str:
    return (f"==== attempt {attempt} · started {started:{constants.BANNER_TIME_FORMAT}} · "
            f"pid {pid} · resume_seq {resume_seq} ====")


def crash_marker(attempt: int, last_ts: float) -> str:
    when = datetime.fromtimestamp(last_ts).astimezone()
    return (f"---- attempt {attempt} ended at {when:{constants.TRANSCRIPT_TIME_FORMAT}} without run.end "
            f"(process exited) ----")


def _pair(key: str, value: Any) -> str:
    if isinstance(value, str) and (" " in value or not value):
        return f'{key}="{value}"'
    return f"{key}={value}"


def _render_args(args: dict) -> str:
    return " ".join(_pair(k, v) for k, v in args.items())


def _money(value: Any) -> str:
    return f"${float(value):.4f}"


def _seconds(ms: Any) -> str:
    return f"{float(ms) / 1000:.1f}s"


def _detail(event: Event) -> tuple[str, str | None]:
    p = dict(event.payload)
    parts: list[str] = []
    block: str | None = p.pop("preview", None) or p.get("text")
    handled = set(constants.RENDERED_PAYLOAD_KEYS)

    def take(*keys: str) -> None:
        handled.update(keys)

    if event.type == EventType.RUN_START:
        take("session_id", "framework", "framework_version", "model")
        if p.get("session_id"):
            parts.append(f"session={p['session_id']}")
        if p.get("framework"):
            version = p.get("framework_version")
            parts.append(f"framework={p['framework']}" + (f"@{version}" if version else ""))
        if p.get("model"):
            parts.append(f"model={p['model']}")
    elif event.type == EventType.RUN_RESUME:
        take("attempt", "resume_seq", "reason")
        parts.append(f"attempt={p.get('attempt')}")
        parts.append(f"from=#{int(p.get('resume_seq', 0)):04d}")
        if p.get("reason"):
            parts.append(f"reason={p['reason']}")
    elif event.type == EventType.RUN_END:
        take("cost_usd", "llm_calls", "tool_calls", "errors")
        parts.append(str(event.status))
        if event.dur_ms is not None:
            parts.append(f"{_seconds(event.dur_ms)} active")
        parts.append(_money(p.get("cost_usd", 0)))
        parts.append(f"{p.get('llm_calls', 0)} llm")
        parts.append(f"{p.get('tool_calls', 0)} tool")
        parts.append(f"{p.get('errors', 0)} errors")
    elif event.type == EventType.AGENT_START:
        parts.append(f"parent=#{event.parent_seq:04d}" if event.parent_seq else "parent=-")
    elif event.type == EventType.AGENT_END:
        take("cost_usd")
        parts.append(str(event.status))
        if event.dur_ms is not None:
            parts.append(_seconds(event.dur_ms))
        if p.get("cost_usd") is not None:
            parts.append(_money(p["cost_usd"]))
    elif event.type == EventType.LLM_PROMPT:
        take("messages", "tokens_in")
        if p.get("messages"):
            parts.append(f"{p['messages']} msgs")
        if p.get("tokens_in"):
            parts.append(f"{p['tokens_in']} tok")
    elif event.type == EventType.LLM_RESPONSE:
        take("stop_reason", "tokens_out", "cost_usd")
        if p.get("stop_reason"):
            parts.append(f"stop={p['stop_reason']}")
        if p.get("tokens_out"):
            parts.append(f"{p['tokens_out']} tok")
        if p.get("cost_usd") is not None:
            parts.append(_money(p["cost_usd"]))
    elif event.type == EventType.TOOL_CALL:
        take("args")
        args = p.get("args") or {}
        rendered = _render_args(args)
        if len(rendered) <= constants.INLINE_ARG_LIMIT:
            if rendered:
                parts.append(rendered)
        else:
            # Never shorten an argument: the whole call moves into the block.
            block = json.dumps(args, indent=2, default=str)
            parts.append(f"{len(args)} args")
    elif event.type == EventType.TOOL_RESULT:
        if event.status:
            parts.append(event.status)
    elif event.type in (EventType.TOOL_ERROR, EventType.ERROR):
        take("error_type", "error")
        parts.append(f"{p.get('error_type', 'Error')}: {p.get('error', '')}")
    elif event.type == EventType.LOG:
        take("level", "logger", "message")
        parts.append(f"{p.get('level', 'INFO')} {p.get('message', '')}")
        handled.add("logger")

    for key, value in p.items():
        if key in handled or value is None:
            continue
        parts.append(_pair(key, value))

    if p.get("text_ref"):
        parts.append(f"{size(p.get('bytes', 0))} → {p['text_ref']}")


    return " · ".join(parts), block


def format_event(event: Event, delta_s: float) -> str:
    when = datetime.fromtimestamp(event.ts).astimezone()
    detail, block = _detail(event)
    line = (f"{event.anchor} {when:{constants.TRANSCRIPT_TIME_FORMAT}}.{when.microsecond // 1000:03d} "
            f"{f'{delta_s:+.1f}s':>6}  {event.type:<13} {(event.name or '-'):<12} "
            f"{detail}").rstrip()
    if block is not None and "\n" not in block and len(block) <= constants.INLINE_BLOCK_LIMIT \
            and not event.payload.get("text_ref"):
        return (line + (" · " if detail else "") + block).rstrip()
    if block is None:
        return line
    if event.payload.get("text_ref"):
        head = f"┌── first {len(block.splitlines())} lines "
        foot = f"└─ truncated · full text: {event.payload['text_ref']} "
    else:
        head = "┌"
        foot = f"└─ {event.anchor} end · {size(event.payload.get('bytes', len(block.encode())))} "
    return "\n".join([
        line,
        head.ljust(constants.FRAME_WIDTH, "─") if head != "┌"
        else "┌" + "─" * (constants.FRAME_WIDTH - 1),
        block,
        foot.ljust(constants.FRAME_WIDTH, "─"),
    ])


class TranscriptWriter:
    """Append, never truncate: a run_id reused after a crash keeps whatever an
    earlier attempt logged, and a resumed attempt adds below its own banner."""

    def __init__(self, run_dir: Path, banner: str, crash: str | None = None):
        path = Path(run_dir) / constants.TRANSCRIPT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("a")
        if crash:
            self._handle.write(f"\n{crash}\n")
        if path.stat().st_size:
            self._handle.write("\n")
        self._handle.write(banner + "\n\n")
        self._handle.flush()
        self._prev_ts: float | None = None

    def __call__(self, event: Event) -> None:
        delta = 0.0 if self._prev_ts is None else event.ts - self._prev_ts
        self._prev_ts = event.ts
        text = format_event(event, delta)
        self._handle.write(text + ("\n\n" if "\n" in text else "\n"))
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()
