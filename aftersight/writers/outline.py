"""`outline.md`, the folded map an agent reads first.

Thirty lines that explain a five-thousand-line run, every row carrying the
`#seq` anchor to jump to in `agent.logs`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aftersight import constants
from aftersight.constants import EventType
from aftersight.events.schemas import Event
from aftersight.utils import size
from aftersight.writers.trace import read_events

def _clock(ts: float) -> str:
    return f"{datetime.fromtimestamp(ts).astimezone():{constants.TRANSCRIPT_TIME_FORMAT}}"


def _row(anchor: int, label: str, dur_ms, cost, status: str) -> str:
    duration = "" if dur_ms == "" else (f"{dur_ms / 1000:.1f}s" if dur_ms is not None else "-")
    money = f"${cost:.4f}" if cost is not None else ""
    return f"#{anchor:04d} {label:<{constants.OUTLINE_NAME_COL}}{duration:>6}  {money:<9}{status}".rstrip()


def render(events: list[Event], summary: dict) -> str:
    if not events:
        return "# empty run\n"
    rows: dict[int, str] = {}
    open_agents: dict[str, int] = {}
    open_tools: dict[str, int] = {}
    pending: dict[int, list] = {}
    failures: list[str] = []
    attempts: dict[int, list[Event]] = {}
    closers: dict[int, int] = {}  # opening seq -> closing seq

    for event in events:
        attempts.setdefault(event.attempt, []).append(event)
        name = event.name or "-"
        if event.type == EventType.AGENT_START:
            open_agents[name] = event.seq
            pending[event.seq] = ["▶ " + name, None, None, "running"]
        elif event.type == EventType.AGENT_END:
            seq = open_agents.pop(name, None)
            if seq is not None:
                closers[seq] = event.seq
                pending[seq][1:] = [event.dur_ms, event.payload.get("cost_usd"),
                                    event.status or "ok"]
        elif event.type == EventType.TOOL_CALL:
            open_tools[name] = event.seq
            pending[event.seq] = ["  → " + name, None, None, "running"]
        elif event.type in (EventType.TOOL_RESULT, EventType.TOOL_ERROR):
            seq = open_tools.pop(name, None)
            detail = event.status or "ok"
            if event.payload.get("error_type"):
                detail = f"✗ {event.payload['error_type']}"
                failures.append(f"#{event.seq:04d}")
            if seq is not None:
                closers[seq] = event.seq
                pending[seq][1:] = [event.dur_ms, None, f"{detail:<24} ← #{event.seq:04d}".rstrip()]
        elif event.type == EventType.ERROR:
            failures.append(f"#{event.seq:04d}")
            pending[event.seq] = [
                f"✗ {event.payload.get('error_type', 'Error')}: {event.payload.get('error', '')}",
                "", None, f"← #{event.seq:04d}"]

    for seq, (label, dur, cost, status) in pending.items():
        rows[seq] = _row(seq, label, dur, cost, status)

    head = summary
    lines = [
        f"# run {head.get('run_id')} · {head.get('status')} · "
        f"{head.get('active_sec')}s active · ${head.get('cost', {}).get('cost_usd', 0):.4f} · "
        f"{head.get('llm_calls')} llm · {head.get('tool_calls')} tool · "
        f"{len(head.get('errors', []))} errors",
        f"session {head.get('session_id') or '-'} · "
        f"{head.get('framework') or '-'}{'@' + head['framework_version'] if head.get('framework_version') else ''} · "
        f"{head.get('model') or '-'} · {head.get('attempts')} attempts · {head.get('wall_sec')}s wall",
    ]
    task = events[0].payload.get("task")
    if task:
        lines += ["", f"task: {task}"]

    for attempt, group in sorted(attempts.items()):
        ended = group[-1]
        outcome = ended.status if ended.type == EventType.RUN_END else "crashed (no run.end)"
        lines += ["", f"---- attempt {attempt} · {_clock(group[0].ts)} → "
                      f"{_clock(group[-1].ts)} · {outcome} ----"]
        lines += [rows[e.seq] for e in group if e.seq in rows]

    lines.append("")
    if failures:
        lines.append(f"failures:  {' '.join(failures)}")
    # Anchor a slow step to the row that opened it, not to the event that closed it.
    opened_by = {end: start for start, end in closers.items()}
    steps = sorted((e for e in events if e.dur_ms and not e.type.startswith("run.")),
                   key=lambda e: -e.dur_ms)[:3]
    if steps:
        lines.append("slowest:   " + " · ".join(
            f"#{opened_by.get(e.seq, e.seq):04d} {e.name or e.type} {e.dur_ms / 1000:.1f}s"
            for e in steps))
    priciest = sorted((e for e in events if e.payload.get("cost_usd")
                       and e.type not in (EventType.RUN_END, EventType.AGENT_END)),
                      key=lambda e: -e.payload["cost_usd"])[:3]
    if priciest:
        lines.append("costliest: " + " · ".join(
            f"#{e.seq:04d} {e.name} ${e.payload['cost_usd']:.4f}" for e in priciest))
    biggest = max((e for e in events if e.payload.get("bytes")),
                  key=lambda e: e.payload["bytes"], default=None)
    if biggest is not None and biggest.payload.get("text_ref"):
        lines.append(f"biggest:   #{biggest.seq:04d} {biggest.name} "
                     f"{size(biggest.payload['bytes'])} → {biggest.payload['text_ref']}")
    return "\n".join(lines) + "\n"


def write(run_dir: Path, summary: dict) -> None:
    events = list(read_events(run_dir))
    (Path(run_dir) / constants.OUTLINE_FILE).write_text(render(events, summary))
