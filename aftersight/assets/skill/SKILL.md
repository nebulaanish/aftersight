---
name: aftersight
description: Use when investigating how this project's agent behaved: a failed or slow agent run, a recurring tool failure, unexpected model output, rising cost, or any question about what an agent actually sent and received. Reads the execution traces in .runs/.
---

# Reading this project's agent traces

Agent runs in this repo record to `.runs/`. That directory is the evidence for
what an agent actually did. Read it before theorising about behaviour.

Start with `.runs/NAVIGATE.md`. It documents the layout, the `#seq` anchor
scheme and a set of verified `rg`/`jq` recipes.

## The loop

1. `.runs/index.jsonl` holds one line per run. Pick the run.
2. `.runs/runs/<run_id>/outline.md` is the folded map. Find the `#seq` that
   matters.
3. `.runs/runs/<run_id>/agent.logs` at that anchor has the exact prompt,
   completion, tool arguments or traceback.

## Rules that keep answers correct

- Aggregate before you read. One run shows an incident; `runs/*/trace.jsonl`
  shows whether it is systemic.
- Glob as `runs/*/…`. `latest` and `sessions/` are symlinks into `runs/`, so
  globbing the root double-counts.
- Count failures by `payload.error_type`, not `status == "error"`, because
  `agent.end` carries that status too.
- Exclude `run.*` when ranking slow steps; `run.end` holds the run total.
- A prompt over 8 KB lives in `blobs/` as plain text. Grep it like any file.
- Sequence numbers continue across a resumed session, and an attempt that died
  without `run.end` is marked as such. A crash and a clean failure are different
  findings.

## When asked to improve the agent

Ground every claim in an anchor. "Tool `x` timed out in 4 of the last 9 runs
(`#0044`, `#0071`, …)" is actionable; "the executor seems flaky" is not.
