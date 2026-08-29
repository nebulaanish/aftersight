# Quickstart

## Install

```bash
pip install aftersight
```

OpenTelemetry comes with it. There is no extra to choose and nothing to
initialise.

## Record a run

Either wrap the command you already run:

```bash
aftersight run python my_agent.py
```

Or add one line to your entry point:

```python
import aftersight

aftersight.start()
```

Both print one line to stderr naming the folder they are writing to:

```
aftersight: recording to .runs/runs/20260830_142233_a1b2
```

On the first run, `aftersight` creates `.runs/`, writes `NAVIGATE.md` into it
and adds `.runs/` to your `.gitignore`.

## Look at what you got

```
.runs/
  NAVIGATE.md
  index.jsonl
  latest -> runs/20260830_142233_a1b2
  runs/20260830_142233_a1b2/
    outline.md
    agent.logs
    trace.jsonl
    analytics.json
    meta.json
    blobs/
    artifacts/
```

Start with `outline.md`. It is the folded map of the run:

```
# run 20260830_142233_a1b2 · failed · 74.6s active · $0.0230 · 3 llm · 4 tool · 4 errors
session sess_kaggle_eda_7c · langgraph@0.6.4 · claude-sonnet-5 · 2 attempts

---- attempt 1 · 14:22:33 -> 14:23:14 · crashed (no run.end) ----
#0002 ▶ triage                      2.5s  $0.0005  ok
#0006 ▶ planner                     8.4s  $0.0121  ok
#0011   → read_file                 0.0s           ✗ PermissionError        ← #0012
#0015   → run_python               30.0s           ✗ TimeoutError           ← #0016

failures:  #0012 #0016 #0022 #0023
```

Then jump to any anchor in the full transcript:

```bash
rg -n -A40 '^#0016 ' .runs/latest/agent.logs
```

## Point your coding agent at it

```bash
aftersight skill
```

That writes `.claude/skills/aftersight/SKILL.md`, which tells a coding agent
that this telemetry exists, how the anchors work, and which three counting
mistakes produce wrong answers.

If you do not use skills, this works just as well:

> Read `.runs/NAVIGATE.md`, then tell me which tool fails most often across the
> last ten runs.

## Add detail where you want it

Capture is automatic for instrumented frameworks. Where you want more, the
explicit API nests inside whatever was captured automatically:

```python
with aftersight.span("planner"):
    with aftersight.span("web_search", kind="tool", args={"q": query}) as s:
        s.output = search(query)

@aftersight.trace                      # sync or async
def read_file(path): ...

aftersight.log("cache miss", key=key)
```

## Resume a session

Pass the same `session_id` and the run appends into the same folder under a new
attempt banner, with sequence numbers continuing where they stopped:

```python
aftersight.start(session_id="sess_42")
```

```bash
aftersight run --session sess_42 python my_agent.py
```

An attempt that died without writing `run.end` is marked in the transcript, so
a crash and a clean failure stay distinguishable.
