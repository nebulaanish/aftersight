# Run folder format

This is the contract. A worked example of every file below lives in
[`examples/telemetry_root/`](https://github.com/nebulaanish/aftersight/tree/main/examples/telemetry_root),
regenerated from the real writers by `examples/generate.py`, so it cannot drift
from the implementation.

## Layout

```
.runs/
  NAVIGATE.md                    the map, written on first use
  index.jsonl                    one line per run
  latest -> runs/<run_id>
  sessions/<session_id> -> ../runs/<run_id>
  runs/<YYYYMMDD_HHMMSS_hash>/
    outline.md                   folded map, regenerated at finalize
    agent.logs                   full transcript, append-only across attempts
    trace.jsonl                  one event per line, the source of truth
    analytics.json               status, timings, per-agent cost, errors
    meta.json                    framework, git sha, argv, attempts
    blobs/<sha1>.txt             payloads over blob_max_bytes
    artifacts/                   whatever your app puts there
```

Run ids sort chronologically. Pointers live outside `runs/` so that a
`runs/*/...` glob cannot count a run twice through a symlink.

## agent.logs

One line per event, with framed blocks for multi-line payloads.

```
#0016 14:23:14.000 +30.0s  tool.error    run_python   TimeoutError: exceeded 30s
```

| Column | |
|---|---|
| `#0016` | zero-padded sequence number, the anchor |
| `14:23:14.000` | local time with millisecond precision |
| `+30.0s` | delta from the previous event, not a duration |
| `tool.error` | event type |
| `run_python` | event name, `-` when there is none |
| rest | detail, assembled from the payload |

A payload that is multi-line or long is framed, and the closing line repeats the
anchor so a match inside the block can find both edges:

```
#0004 14:22:35.512  +2.4s  llm.response  triage   stop=end_turn · 386 tok · $0.0005
┌──────────────────────────────────
{"decision": "work"}
└─ #0004 end · 86 B ───────────────
```

A payload over `blob_max_bytes` keeps its first lines inline and points at the
blob:

```
#0007 14:22:35.600  +0.1s  llm.prompt    planner   4 msgs · 69340 tok · 270.9 KB -> blobs/9fa2c1e4.txt
┌── first 12 lines ────────────────
[system]
You are the planner...
└─ truncated · full text: blobs/9fa2c1e4.txt ─
```

Attempts are separated by banners, and an attempt that died without `run.end`
is marked:

```
---- attempt 1 ended at 14:23:14 without run.end (process exited) ----

==== attempt 2 · started 2026-08-30 14:31:02 · pid 48211 · resume_seq 16 ====
```

## trace.jsonl

One JSON object per line.

| Field | |
|---|---|
| `run_id` | folder name |
| `seq` | sequence number, matches the `#0016` anchor |
| `attempt` | which attempt emitted it |
| `ts` | epoch seconds |
| `iso` | local time with offset |
| `type` | event type, see below |
| `name` | agent name, tool name, logger name, or `null` |
| `parent_seq` | enclosing event, or `null` |
| `status` | `ok`, `error`, `failed`, a log level, or `null` |
| `dur_ms` | duration for closing events, run total on `run.end` |
| `payload` | type-specific, see below |

## Event types

| Type | Payload keys |
|---|---|
| `run.start` | `session_id`, plus any metadata passed to `start()` |
| `run.resume` | `attempt`, `resume_seq`, `reason` |
| `run.end` | `cost_usd`, `llm_calls`, `tool_calls`, `errors` |
| `agent.start` | fields passed to `span()` |
| `agent.end` | `cost_usd` when set, a rollup rather than a new cost |
| `llm.prompt` | `messages`, `tokens_in`, `model`, `text` or `text_ref` + `preview`, `bytes` |
| `llm.response` | `stop_reason`, `tokens_out`, `cost_usd`, `text` |
| `tool.call` | `args` |
| `tool.result` | `text` and anything set on the span handle |
| `tool.error` | `error_type`, `error` |
| `error` | `error_type`, `error`, `text` for a traceback |
| `log` | `level`, `message`, plus your fields |

Types are dotted on purpose: `rg 'tool\.'` finds all tool activity and
`rg '\.error'` finds every failure shape.

## analytics.json

```json
{
  "run_id": "20260830_142233_a1b2",
  "session_id": "sess_kaggle_eda_7c",
  "status": "failed",
  "framework": "langgraph",
  "model": "claude-sonnet-5",
  "started_at": "2026-08-30T14:22:33+05:45",
  "ended_at": "2026-08-30T14:31:35.620+05:45",
  "wall_sec": 542.62,
  "active_sec": 74.62,
  "attempts": 2,
  "llm_calls": 3,
  "tool_calls": 4,
  "tool_calls_by_name": {"web_search": 1, "read_file": 1, "run_python": 2},
  "errors": [
    {"seq": 12, "type": "PermissionError", "name": "read_file", "message": "..."}
  ],
  "cost": {
    "input_tokens": 72993,
    "output_tokens": 2482,
    "cost_usd": 0.023,
    "by_agent": {"triage": {"llm_calls": 1, "cost_usd": 0.0005}}
  }
}
```

`wall_sec` spans the whole session including the gap between attempts.
`active_sec` sums only the time attempts were running.

## meta.json

Framework, `python`, `platform`, `cwd`, `argv`, `git` (`sha`, `branch`,
`dirty`), `tags`, and an `attempts` list recording `n`, `pid`, `started_at`,
`ended_at`, `last_seq` and `outcome` for each attempt. `outcome` is `crashed`
for an attempt that never wrote `run.end`.

## index.jsonl

One line per run, rewritten in place when a run finalises.

```json
{"run_id": "...", "session_id": "...", "started_at": "...", "status": "failed",
 "active_sec": 74.62, "cost_usd": 0.023, "llm_calls": 3, "tool_calls": 4,
 "errors": 4, "framework": "langgraph", "model": "claude-sonnet-5",
 "last_error": "RuntimeError: executor gave up after 2 attempts"}
```

## Invariants

Anything reading these files can rely on the following.

- `#seq` is zero-padded to four digits and identical across `outline.md`,
  `agent.logs` and `trace.jsonl`. It never resets, never repeats, and continues
  across a resume.
- Column 3 of `agent.logs` is a delta, not a duration.
- A framed block repeats its anchor on the closing line.
- `status: "error"` appears on `agent.end` as well as on real failures, so
  count failures by `payload.error_type`.
- `dur_ms` on `run.end` is the run total, so exclude `run.*` when ranking steps.
- `agent.end` carries a cost rollup, so sum leaf costs or read
  `analytics.json`, never both.
- Nothing is truncated. A payload not inline is in `blobs/`, in full.
