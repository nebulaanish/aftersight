# Python API

Six functions. Only `start()` is required.

```python
import aftersight
```

## start

```python
aftersight.start(session_id=None, *, tags=(), **kwargs) -> Run
```

Begins recording and returns the [`Run`](#run). Safe to call more than once: a
second call while a run is active returns the run that is already going, so
calling it from several entry points is harmless.

Use it bare for a run that is finalised when the process exits, or as a context
manager to scope it yourself:

```python
aftersight.start()                          # finalised at interpreter exit

with aftersight.start(session_id="eval-42") as run:
    ...                                     # finalised on the way out
```

**`session_id`** ties a run to a session. Passing one that has run before
appends into the same folder under a new attempt banner, with sequence numbers
continuing where they stopped.

**`tags`** is a tuple of strings recorded in `meta.json`.

**`**kwargs`** is split two ways. Anything matching a
[configuration](configuration.md) field configures the run. Everything else is
free-form metadata, recorded in `meta.json` and in the `run.start` event, and
surfaced in `outline.md` and `index.jsonl`:

```python
aftersight.start(
    session_id="eval-42",
    keep_runs=200,                    # configuration
    framework="langgraph",            # metadata
    framework_version="0.6.4",
    model="claude-sonnet-5",
    task="plot the variance explained curve",
)
```

`framework`, `framework_version`, `model` and `task` are the metadata keys the
outline and index render specially. Any other key is still recorded.

When `AFTERSIGHT=0`, `start()` returns an inert object with the same interface
and nothing is written to disk.

## span

```python
aftersight.span(name, kind="agent", **fields) -> context manager
```

Records a step. `kind="agent"` emits `agent.start` and `agent.end`;
`kind="tool"` emits `tool.call` and then `tool.result` or `tool.error`. Spans
nest, and nest correctly inside spans captured from OpenTelemetry.

`**fields` go on the opening event, which is where tool arguments belong:

```python
with aftersight.span("web_search", kind="tool", args={"q": query}) as s:
    s.output = search(query)
```

The yielded handle has:

- **`s.output = value`** sets the payload text of the closing event. A
  non-string is stored with `repr()`.
- **`s.set(**fields)`** adds arbitrary fields to the closing event, for example
  `s.set(results=12, cost_usd=0.0104)`.

An exception propagates after being recorded, with the traceback attached. It
is marked as already recorded, so it is not logged a second time by the
excepthook when it reaches the top.

If no run is active, `span()` starts one.

## trace

```python
@aftersight.trace
@aftersight.trace(kind="tool", name=None)
```

Decorator form of `span()`, for sync and async functions alike. Arguments are
bound to their parameter names and recorded, and the return value becomes the
output.

```python
@aftersight.trace
def web_search(query: str) -> str: ...

@aftersight.trace(kind="agent", name="planner")
async def plan(task: str) -> Plan: ...
```

## log

```python
aftersight.log(message, level="INFO", **fields) -> None
```

Records a `log` event. Pass `logger="name"` to set the event name, which
otherwise defaults to `app`.

```python
aftersight.log("cache miss", key=key)
aftersight.log("retrying", level="WARNING", attempt=2)
```

Warnings and exceptions from the stdlib `logging` module are captured
automatically, so this is for notes your own code wants in the transcript.

## current

```python
aftersight.current() -> Run | None
```

The active run, or `None`.

## artifact_dir

```python
aftersight.artifact_dir() -> Path
```

`runs/<run_id>/artifacts/`. Anything you drop in there is kept beside the trace
and never parsed, which makes it the right home for a final answer, a plot, or
a dumped state file.

```python
(aftersight.artifact_dir() / "answer.md").write_text(answer)
```

## Run

Returned by `start()` and `current()`.

| Attribute | |
|---|---|
| `run_id` | `20260830_142233_a1b2` |
| `session_id` | as passed to `start()`, or `None` |
| `dir` | `Path` of the run folder |
| `attempt` | 1 on a fresh run, higher on a resumed session |
| `artifacts` | `Path` of the artifacts directory |
| `finalized` | whether the run has been closed |
| `config` | the resolved `Config` |

```python
run.finalize(status=None)
```

Writes `run.end`, regenerates `analytics.json` and `outline.md`, updates
`index.jsonl` and `meta.json`, and prunes old runs. Called automatically at
interpreter exit and on context manager exit. With `status=None` the outcome is
derived from whether anything errored.

## Failure behaviour

No call in this module raises into your code. Failures are reported to the
`aftersight` logger and the run continues. A writer that throws is logged and
skipped rather than taking down the emit path.
