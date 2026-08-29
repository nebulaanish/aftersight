# Configuration

Every field has a working default. Nothing needs to be set for the package to
work.

## Precedence

Defaults, then environment variables, then keyword arguments to `start()`.

```python
aftersight.start(keep_runs=200, quiet=True)
```

```bash
export AFTERSIGHT_KEEP_RUNS=200
export AFTERSIGHT_QUIET=1
```

## Fields

| Field | Environment variable | Default | |
|---|---|---|---|
| `enabled` | `AFTERSIGHT` | `1` | `0` disables everything. No folders are created and every call is inert. |
| `root` | `AFTERSIGHT_ROOT` | `.runs` | Where runs are written. |
| `keep_runs` | `AFTERSIGHT_KEEP_RUNS` | `50` | Oldest run folders are pruned past this at the start of a run. `0` keeps everything. |
| `blob_max_bytes` | `AFTERSIGHT_BLOB_MAX` | `8192` | Payloads larger than this move to `blobs/`. |
| `blob_preview_lines` | | `12` | Lines of a spilled payload kept inline in the transcript. |
| `capture_otel` | `AFTERSIGHT_OTEL` | `1` | Install the OpenTelemetry span processor. |
| `capture_logging` | `AFTERSIGHT_LOGGING` | `1` | Install the stdlib `logging` bridge. |
| `log_level` | | `WARNING` | Threshold for the logging bridge. |
| `redact` | `AFTERSIGHT_REDACT` | `1` | Scrub credentials before writing. |
| `quiet` | `AFTERSIGHT_QUIET` | `0` | Suppress the one-line startup notice. |

Boolean environment variables accept `1/0`, `true/false`, `yes/no`, `on/off`.

## Turning it off

`AFTERSIGHT=0` is a hard off switch. `start()` returns an inert object, no
directory is created, and `span()`, `trace` and `log()` do nothing. This is the
intended way to run the same code in an environment where you do not want
traces on disk.

## Bounding disk use

Two knobs. `keep_runs` bounds how many run folders survive, and
`blob_max_bytes` decides when a large payload stops being inlined into the
transcript. Neither is a hard size cap, because nothing is ever truncated. If
you record a run with a 40 MB prompt, that 40 MB is on disk.

## Metadata versus configuration

Keyword arguments to `start()` that are not configuration fields are recorded as
run metadata:

```python
aftersight.start(
    keep_runs=200,               # configuration
    framework="langgraph",       # metadata, ends up in meta.json and outline.md
    model="claude-sonnet-5",
)
```

`framework`, `framework_version`, `model` and `task` are rendered specially in
`outline.md` and `index.jsonl`. Any other key is still recorded, just not
formatted.

## Redaction

Applied at the sink, so it covers every writer at once. It matches
`sk-` prefixed keys, bearer tokens, `api_key` / `secret` / `token` / `password`
assignments, GitHub tokens and AWS access key ids, replacing the value with
`[REDACTED]`.

It is a filter, not a guarantee. Treat run folders as containing whatever your
prompts contained.
