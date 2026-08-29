"""`analytics.json`, the run summarised, regenerated from `trace.jsonl`.

Regenerated rather than accumulated in memory, so a run that crashed and was
resumed still summarises every attempt.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from aftersight import constants
from aftersight.constants import EventType
from aftersight.events.schemas import Event
from aftersight.writers.trace import read_events


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat()


def summarise(events: list[Event]) -> dict:
    if not events:
        return {}
    first, last = events[0], events[-1]
    start = dict(first.payload)

    owners: dict[int, str] = {e.seq: e.name or "-" for e in events
                              if e.type == EventType.AGENT_START}

    def owner(event: Event) -> str:
        return owners.get(event.parent_seq or -1, event.name or "-")

    by_agent: dict[str, dict] = defaultdict(
        lambda: {"llm_calls": 0, "tool_calls": 0, "input_tokens": 0,
                 "output_tokens": 0, "cost_usd": 0.0})
    tools_by_name: dict[str, int] = defaultdict(int)
    errors, spans = [], defaultdict(list)
    llm_calls = tool_calls = 0
    tokens_in = tokens_out = 0
    cost = 0.0

    for event in events:
        spans[event.attempt].append(event.ts)
        agent = by_agent[owner(event)]
        if event.type == EventType.LLM_PROMPT:
            llm_calls += 1
            agent["llm_calls"] += 1
            tokens_in += event.payload.get("tokens_in") or 0
            agent["input_tokens"] += event.payload.get("tokens_in") or 0
        elif event.type == EventType.LLM_RESPONSE:
            tokens_out += event.payload.get("tokens_out") or 0
            agent["output_tokens"] += event.payload.get("tokens_out") or 0
        elif event.type == EventType.TOOL_CALL:
            tool_calls += 1
            agent["tool_calls"] += 1
            tools_by_name[event.name or "-"] += 1
        # agent.end and run.end carry rollups; only leaf costs are summed, or the
        # same dollar is counted at every level of the tree.
        if event.type not in (EventType.RUN_END, EventType.AGENT_END) \
                and event.payload.get("cost_usd"):
            cost += event.payload["cost_usd"]
            agent["cost_usd"] += event.payload["cost_usd"]
        if event.payload.get("error_type"):
            errors.append({"seq": event.seq, "type": event.payload["error_type"],
                           "name": event.name, "message": event.payload.get("error", "")})

    # agent.end carries the agent's own rollup; prefer it over summing children.
    for event in events:
        if event.type == EventType.AGENT_END and event.payload.get("cost_usd") is not None:
            by_agent[event.name or "-"]["cost_usd"] = event.payload["cost_usd"]

    active = sum(max(ts) - min(ts) for ts in spans.values())
    status = last.status if last.type == EventType.RUN_END else "crashed"
    return {
        "run_id": first.run_id,
        "session_id": start.get("session_id"),
        "status": status,
        "framework": start.get("framework"),
        "framework_version": start.get("framework_version"),
        "model": start.get("model"),
        "started_at": _iso(first.ts),
        "ended_at": _iso(last.ts),
        "wall_sec": round(last.ts - first.ts, 2),
        "active_sec": round(active, 2),
        "attempts": len(spans),
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "tool_calls_by_name": dict(tools_by_name),
        "errors": errors,
        "cost": {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost_usd": round(cost, 6),
            # tool spans become their own "owner" when they sit outside an agent;
            # keep only entries that actually did something worth attributing.
            "by_agent": {k: v for k, v in by_agent.items()
                         if k != "-" and (v["llm_calls"] or v["cost_usd"])},
        },
    }


def write(run_dir: Path) -> dict:
    data = summarise(list(read_events(run_dir)))
    (Path(run_dir) / constants.ANALYTICS_FILE).write_text(json.dumps(data, indent=2) + "\n")
    return data
