# Architecture

Where each kind of code lives. This is binding: a file in the wrong folder is a bug.

## Conventions (adopted from agno)

1. **Feature folders, not layer folders.** `events/`, `run/`, `writers/`. Never a global `models/` + `services/` split.
2. **Fixed file roles.** Inside a feature: `schemas.py` = data shapes, `setup.py` = the one-call entry point, everything else = one concern per file.
3. **`__init__.py` only re-exports**, with an explicit `__all__`. It contains no logic. Leaf modules import siblings by full path, never through a package `__init__` (circular imports).
4. **Plain dataclasses with explicit `to_dict`/`from_dict`.** No pydantic in the data layer.
5. **Optional third-party imports live behind `try/except ImportError`** with a module-level `_AVAILABLE` flag and an error message naming the exact `pip install`.
6. **Cross-cutting helpers are functions in `utils.py`**, not objects.

## Rules (ours)

- **Data shapes only in a `schemas.py`.** No dataclass is defined anywhere else.
- **Constants only in `constants.py`.** File names, layout widths, defaults,
  environment variable names, redaction patterns and the OpenTelemetry
  attribute tables all live there. A literal filename or magic number anywhere
  else is a bug: the run folder layout is a published contract, and it should be
  readable in one file rather than reconstructed from twelve.
- **Utilities only in `utils.py`.** Logging, redaction and formatting helpers
  that know nothing about runs or events. Anything that knows about a run
  belongs to the module that owns that concept.
- **Disk writes only in `writers/` and `run/store.py`.** No `open()` / `Path.write_*` elsewhere.
- **Optional dependencies only in `integrations/`.** The core never imports opentelemetry.
- **Never raise into the host app.** Every public entry point catches, logs via `utils`, and continues. Broken telemetry must not break an agent run.
- **No ABC until there is a second implementation.** There is one storage backend: the filesystem.
- **Integrations are idempotent.** A tracer provider cannot have a processor
  removed, so a second `start()` re-points the installed one instead of stacking
  another.
- **No truncation in `writers/transcript.py`.** Oversized payloads spill to `blobs/`; they are never silently shortened.

## Adoption rules

Ease of adoption outranks every other consideration here. It is not a
breakthrough project; it is only used if it is trivial to start.

- **One required call.** `aftersight.start()`, or none at all via
  `aftersight run`. Everything else (`span`, `trace`, `log`) is optional depth
  a user reaches for later.
- **No setup step.** The telemetry root, `NAVIGATE.md` and the `.gitignore` entry
  are created on first use. There is no `init` to discover or forget.
- **No optional extras to figure out.** OpenTelemetry is a hard dependency so
  that `pip install aftersight` is the whole install.
- **Nothing to configure.** Every `Config` field has a working default;
  environment variables and `start()` arguments are the only two ways to change
  one, and neither is ever required.
- **Say something.** One line to stderr on start, naming the folder. Silent
  instrumentation reads as broken instrumentation.

## Tree

```
aftersight/
  __init__.py          public API re-exports: start, span, trace, log, current, artifact_dir
  constants.py         every constant: file names, layout, defaults, env vars, OTel dialects
  utils.py             logging, redaction, size formatting
  config.py            Config dataclass; defaults, then env, then start() arguments
  autostart.py         entry point for `aftersight run`
  cli.py               run | skill

  events/
    schemas.py         Event dataclass
    sink.py            seq allocation, thread-safe emit, fan-out to writers

  run/
    api.py             contextvars + public start() / span() / trace / log()
    run.py             Run: dir resolution, session resume, attempt banner, finalize
    store.py           read side: root creation, index.jsonl, pointers, retention

  writers/             registered in this order; BlobWriter normalises the payload
    blobs.py           blobs/<sha1>.txt spill above config.blob_max_bytes
    transcript.py      agent.logs   framed blocks, #seq anchors, no truncation
    trace.py           trace.jsonl  one event per line; the source of truth
    outline.py         outline.md   folded map, regenerated at finalize
    analytics.py       analytics.json  status, timings, per-agent cost, errors

  integrations/
    otel.py            SpanProcessor + setup_tracing(); reads the dialect tables
    stdlog.py          logging.Handler bridge (WARNING+ by default)

  assets/
    NAVIGATE.md        written into the telemetry root on first use
    skill/SKILL.md     Claude Code skill installed by `aftersight skill`

examples/generate.py       regenerates the fixture below from the real writers
examples/telemetry_root/   worked fixture, the format spec, see below
tests/test_formats.py      asserts the invariants the NAVIGATE.md recipes rely on
```

## Run directory

Pointers live outside `runs/` so that `runs/*/...` globs cannot double-count a
run through `latest` or `sessions/`.

```
<root>/                          default .runs/, gitignored
  NAVIGATE.md                    the agent's map + rg/jq recipes
  index.jsonl                    one line per run: status, cost, duration, error, tags
  latest -> runs/<run_id>
  sessions/<session_id> -> ../runs/<run_id>
  runs/<YYYYMMDD_HHMMSS_hash>/
    outline.md                   folded map, regenerated at finalize, read first
    agent.logs                   full transcript, append-only across attempts
    trace.jsonl                  machine view, carries parent_seq
    analytics.json               status, timings, per-agent cost, error list
    meta.json                    framework, git sha, argv, tags, attempts[]
    blobs/<sha1>.txt             payloads above config.blob_max_bytes
    artifacts/                   host app drops whatever it wants
```

A worked example of every one of these files lives in `examples/telemetry_root/`
at the repository root.
It is the format spec: the writers are built to reproduce it, and the recipes in
its `NAVIGATE.md` are verified against it.

## Format invariants

- `#seq` is zero-padded to 4 and is the same number in `outline.md`,
  `agent.logs` and `trace.jsonl`. It never resets, never repeats, and survives
  a resume.
- Column 3 of `agent.logs` is the delta from the previous event, not a duration.
- A framed block repeats its anchor on the closing line, so a hit landing inside
  it can find both edges.
- `status: "error"` appears on `agent.end` too. Anything counting failures must
  filter on `payload.error_type`.
- `dur_ms` is present on `run.end` (the run total). Anything ranking steps must
  exclude `run.*`.
