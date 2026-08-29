# Navigating these runs

You are a coding agent. This directory is the execution history of the agent
system in this repo. Read this file once, then use `rg` and `jq`.

## Layout

```
index.jsonl                one line per run, start here for "which run?"
latest -> runs/<run_id>    most recent run
sessions/<session_id>      -> the run folder that session resumed into
runs/<run_id>/
  outline.md               folded map of the run, read this first
  agent.logs               full transcript, nothing truncated
  trace.jsonl              same events, machine-readable, has parent_seq
  analytics.json           status, timings, per-agent cost, error list
  meta.json                framework, git sha, argv, attempts[]
  blobs/<sha>.txt          payloads over 8 KB, plain text
  artifacts/               whatever the app chose to keep
```

Run ids are `YYYYMMDD_HHMMSS_hash`, so they sort chronologically. Glob run
files as `runs/*/...` and never from the root: `latest` and `sessions/` are
symlinks into `runs/`, so a root glob counts every run twice.

## The three-step loop

1. **Which run?** `index.jsonl`
2. **What happened in it?** `runs/<run_id>/outline.md`, then jump to a `#seq`
3. **Exactly what went in and out?** `runs/<run_id>/agent.logs` at that `#seq`

## Anchors

Every event has a zero-padded sequence number. It is the same number in
`outline.md`, `agent.logs` and `trace.jsonl`, so you can move between them:

```sh
rg -n '^#0016 ' latest/agent.logs          # jump to one event
rg -n '#0016' runs/<run_id>/               # every mention of it
```

Multi-line payloads are framed. The closing line repeats the anchor, so a hit
landing inside a block can find both edges:

```
#0004 14:22:35.512  +2.4s  llm.response  triage   stop=end_turn · 386 tok · $0.0005
┌──────────────────────────────────
{"decision": "work", ...}
└─ #0004 end · 86 B ───────────────
```

Column 3 is the delta from the previous event. Scan it to find slow steps. A
negative delta means an event whose span declared its kind late and was therefore
placed at its end rather than its start; the timestamp is still correct.

## Recipes

```sh
# failed runs, newest last
jq -r 'select(.status!="ok") | "\(.run_id) \(.errors) errs $\(.cost_usd) \(.last_error)"' index.jsonl

# the most common failure across all history
rg -oN '"error_type": "[A-Za-z]+"' runs/*/trace.jsonl | cut -d'"' -f4 | sort | uniq -c | sort -rn

# every error in one run, with its anchor
#   filter on payload.error_type, not .status, agent.end also carries status "error"
jq -r 'select(.payload.error_type) | "#\(.seq|tostring|("0000"+.)[-4:]) \(.name) \(.payload.error_type): \(.payload.error)"' latest/trace.jsonl

# what a tool was actually called with, every time
rg -N '^#\d+ .* tool\.call     run_python' runs/*/agent.logs

# read one event and its payload block
rg -n -A40 '^#0023 ' latest/agent.logs

# where the money went
jq -r '.cost.by_agent | to_entries[] | "\(.key) $\(.value.cost_usd)"' latest/analytics.json

# slowest steps in a run, exclude run.* or the run total wins every time
jq -r 'select(.dur_ms!=null and (.type|startswith("run.")|not)) | "\(.dur_ms)ms #\(.seq|tostring|("0000"+.)[-4:]) \(.type) \(.name)"' latest/trace.jsonl | sort -rn | head

# did this session get resumed, and why did the earlier attempt end?
jq '.attempts' latest/meta.json
rg -n '^==== attempt|^---- attempt' latest/agent.logs

# a prompt too big to inline
rg -n 'blobs/' latest/agent.logs        # find the pointer
rg -n 'PCA' latest/blobs/*.txt          # then grep the blob like any text file

# same failure across runs, or just this one?
rg -lN 'TimeoutError' runs/*/agent.logs
```

## Counting things correctly

Three traps, each of which silently produces a wrong answer rather than an error:

- `status: "error"` appears on `agent.end` too. Count failures by
  `payload.error_type`.
- `run.end` carries the run total in `dur_ms`. Exclude `run.*` when ranking steps.
- `agent.end` carries a cost rollup. Sum leaf costs, or read
  `analytics.json → cost.by_agent`.

## Event types

`run.start` `run.resume` `run.end` · `agent.start` `agent.end` ·
`llm.prompt` `llm.response` · `tool.call` `tool.result` `tool.error` ·
`error` · `artifact` · `log`

Namespaced on purpose: `rg 'tool\.'` gets all tool activity, `rg '\.error'`
gets every failure shape.

## Resume

A session that is resumed appends into the same run folder under a new
`==== attempt N ====` banner. Sequence numbers continue across attempts and
are never reused. An attempt that died without `run.end` is marked
`---- attempt N ended ... without run.end ----`, which is how you tell a crash
from a clean failure.

## When you are looking for a systemic problem

Do not read one run. Aggregate first:

```sh
rg -oN '"error_type": "[A-Za-z]+"' runs/*/trace.jsonl | cut -d'"' -f4 | sort | uniq -c | sort -rn
jq -s 'group_by(.status)[] | {status: .[0].status, n: length}' index.jsonl
```

Then open the cheapest run that shows the pattern, not the biggest.
