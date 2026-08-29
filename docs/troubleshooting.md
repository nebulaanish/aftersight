# Troubleshooting

## No run folder appears

Check that recording is on. `AFTERSIGHT=0` disables everything and creates no
folders.

```bash
env | grep AFTERSIGHT
```

If `start()` cannot create the folder it logs the reason rather than raising,
because broken telemetry must never break an agent run. Turn the logger up to
see it:

```python
import logging
logging.getLogger("aftersight").setLevel(logging.DEBUG)
logging.basicConfig()
```

## The folder exists but only has run.start and run.end

Nothing was captured, which means your framework emits no OpenTelemetry spans
and you have not used the explicit API. See [Frameworks](frameworks.md), and in
particular install the OpenInference instrumentor for your framework if one
exists.

```bash
jq -r '.type' .runs/latest/trace.jsonl | sort | uniq -c
```

## Events appear twice

`start()` was called twice and something re-installed a span processor. Recent
versions re-point the existing processor instead of stacking a second one, so
first check your installed version. If you are calling `start()` from library
code, call it once at your entry point instead: a second call returns the run
that is already active.

## The transcript is missing the prompt text

Two likely causes. Either the framework does not put prompt content on the span
at all, which you can confirm with

```bash
jq -r 'select(.type=="llm.prompt") | .payload | keys' .runs/latest/trace.jsonl
```

or the payload was over 8 KB and moved to `blobs/`, in which case the event line
ends with `-> blobs/<hash>.txt`. Nothing is ever silently dropped.

## A negative delta in column 3

The event belongs to a span that declared its kind after it started, so it was
classified when it ended rather than when it began, and it appears after events
that actually happened later. The timestamp on the line is still correct. Most
instrumentors set attributes at span creation and do not hit this.

## An agent.start with no matching agent.end

The attempt crashed. Look for the crash marker further down the transcript:

```bash
rg -n '^---- attempt' .runs/latest/agent.logs
```

`outline.md` shows the unterminated span with status `running`, and
`meta.json` records the attempt outcome as `crashed`.

## Old runs disappeared

`keep_runs` defaults to 50 and prunes the oldest run folders at the start of
each new run. Raise it, or set it to `0` to keep everything:

```bash
export AFTERSIGHT_KEEP_RUNS=500
```

## A secret ended up in a trace

Redaction covers common shapes (`sk-` keys, bearer tokens, `api_key=` pairs,
GitHub tokens, AWS access key ids) but it is a filter, not a guarantee. If
something got through, delete the run folder and open an issue with the shape of
the credential so the pattern can be added. Redaction runs at the sink, so it
applies to every writer at once.

## .runs/ was committed to git

The `.gitignore` entry is only added when the root is a dotted directory that
resolves inside the repository. If you set `AFTERSIGHT_ROOT` to a visible name
such as `runs/`, that was read as a deliberate choice and the entry is not
added. Add it yourself, or use a dotted root.

## Runs slow the process down

Every event is flushed to disk as it happens, which is what makes a crashed run
still readable. If that cost matters in your loop, the honest answer is that
this is development infrastructure: set `AFTERSIGHT=0` in the environment where
throughput matters.
