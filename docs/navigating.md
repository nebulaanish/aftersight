# Navigating runs

The whole point of the file layout is that `rg` and `jq` are enough. A copy of
this page, trimmed to the recipes, is written into your telemetry root as
`NAVIGATE.md` so a coding agent finds it without being pointed at these docs.

## The three-step loop

1. **Which run?** `index.jsonl`, one line per run.
2. **What happened in it?** `runs/<run_id>/outline.md`, then note a `#seq`.
3. **Exactly what went in and out?** `runs/<run_id>/agent.logs` at that anchor.

## Anchors

Every event carries a zero-padded sequence number that is identical across
`outline.md`, `agent.logs` and `trace.jsonl`.

```bash
rg -n '^#0016 ' .runs/latest/agent.logs      # jump to one event
rg -n -A40 '^#0023 ' .runs/latest/agent.logs # read it with its payload block
```

Multi-line payloads are framed, and the closing line repeats the anchor so a
match landing inside a block can find both edges:

```
#0004 14:22:35.512  +2.4s  llm.response  triage   stop=end_turn · 386 tok · $0.0005
┌──────────────────────────────────
{"decision": "work", ...}
└─ #0004 end · 86 B ───────────────
```

Column 3 is the delta from the previous event, not a duration, so scanning it
down the page finds slow steps with no tooling at all.

## Picking a run

```bash
# failed runs with their last error
jq -r 'select(.status!="ok") | "\(.run_id) \(.errors) errs $\(.cost_usd) \(.last_error)"' .runs/index.jsonl

# how runs are distributed by status
jq -s 'group_by(.status)[] | {status: .[0].status, n: length}' .runs/index.jsonl

# the expensive ones
jq -r '"\(.cost_usd) \(.run_id)"' .runs/index.jsonl | sort -rn | head
```

## Finding a systemic problem

Do not read one run. Aggregate first, then open the cheapest run that shows the
pattern.

```bash
# the most common failure across all history
rg -oN '"error_type": "[A-Za-z]+"' .runs/runs/*/trace.jsonl | cut -d'"' -f4 | sort | uniq -c | sort -rn

# which runs hit a particular failure
rg -lN 'TimeoutError' .runs/runs/*/agent.logs

# what a tool was actually called with, every time it ran
rg -N '^#\d+ .* tool\.call     run_python' .runs/runs/*/agent.logs
```

## Inside one run

```bash
# every failure with its anchor
jq -r 'select(.payload.error_type) | "#\(.seq|tostring|("0000"+.)[-4:]) \(.name) \(.payload.error_type): \(.payload.error)"' .runs/latest/trace.jsonl

# slowest steps
jq -r 'select(.dur_ms!=null and (.type|startswith("run.")|not)) | "\(.dur_ms)ms #\(.seq|tostring|("0000"+.)[-4:]) \(.type) \(.name)"' .runs/latest/trace.jsonl | sort -rn | head

# where the money went
jq -r '.cost.by_agent | to_entries[] | "\(.key) $\(.value.cost_usd)"' .runs/latest/analytics.json

# did this session get resumed, and how did each attempt end
jq '.attempts' .runs/latest/meta.json
rg -n '^==== attempt|^---- attempt' .runs/latest/agent.logs
```

## Large payloads

A payload over 8 KB is written to `blobs/` as plain text, with the first lines
kept inline so the event is still identifiable.

```bash
rg -n 'blobs/' .runs/latest/agent.logs     # find the pointer
rg -n 'PCA' .runs/latest/blobs/*.txt       # then grep the blob like any file
```

## Three ways to get a wrong answer

Each of these silently produces a plausible number rather than an error.

!!! danger "Glob `runs/*/`, never the root"
    `latest` and `sessions/` are symlinks into `runs/`, so a glob at the root
    counts every run twice. This is why run folders live one level down.

!!! danger "Count failures by `payload.error_type`"
    `status: "error"` also appears on `agent.end`, so filtering on status
    inflates the failure count and yields rows with no error attached.

!!! danger "Exclude `run.*` when ranking steps"
    `run.end` carries the run total in `dur_ms`, so it wins any
    slowest-step ranking that does not exclude it.

## Reading a resumed session

Sequence numbers continue across attempts and are never reused. An attempt that
ended without `run.end` is marked:

```
#0016 14:23:14.000 +30.0s  tool.error    run_python   TimeoutError: exceeded 30s

---- attempt 1 ended at 14:23:14 without run.end (process exited) ----

==== attempt 2 · started 2026-08-30 14:31:02 · pid 48211 · resume_seq 16 ====
```

A crash and a clean failure are different findings, so the distinction is worth
keeping in mind when you summarise what went wrong.
