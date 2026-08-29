# aftersight

Local observability built for coding agents to inspect.

## The problem

Coding agents already explore repositories with file search, shell commands and
plain text. Agent telemetry usually lives somewhere else: behind a dashboard,
an API or a remote MCP server.

Aftersight writes the evidence into the repository instead. A coding agent can
use the tools it already knows to:

1. diagnose why one run failed;
2. find failures that recur across runs;
3. inspect the exact inputs and outputs of models and tools.

## Start in one command

```bash
pip install aftersight
aftersight run python my_agent.py
```

No account, API key, service or initialization step is required.

## Ask your coding agent

Each telemetry root includes a `NAVIGATE.md` with verified `rg` and `jq`
recipes. Tell your coding agent:

> Read `.runs/NAVIGATE.md` and find out why the latest run failed.

For Claude Code, the optional command below installs the bundled navigation
skill:

```bash
aftersight skill
```

## What gets recorded

```text
.runs/
  NAVIGATE.md
  index.jsonl
  latest -> runs/<run_id>
  runs/<run_id>/
    outline.md
    agent.logs
    trace.jsonl
    analytics.json
    meta.json
    blobs/
    artifacts/
```

`outline.md` is the short map. `agent.logs` is the complete readable
transcript. `trace.jsonl`, `analytics.json` and `index.jsonl` are stable
machine-readable views for scripts and frontends. The same `#seq` anchor
identifies an event in every projection.

## Use it from Python

```python
import aftersight

aftersight.start()
```

Add explicit detail only where it helps:

```python
with aftersight.span("planner"):
    with aftersight.span("web_search", kind="tool", args={"q": query}) as span:
        span.output = search(query)

@aftersight.trace
def read_file(path): ...

aftersight.log("cache miss", key=key)
```

## Works with OpenTelemetry

Aftersight attaches a span processor to the application's existing
OpenTelemetry setup and reads common `gen_ai.*`, OpenInference and generic
input/output attributes. Frameworks that already emit compatible spans need no
aftersight-specific adapter. An existing tracer provider and its exporters are
left in place.

## How it compares

[LangSmith](https://docs.langchain.com/langsmith/observability-concepts),
[Langfuse](https://langfuse.com/docs/api-and-data-platform/features/observations-api),
[Phoenix](https://arize.com/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/extract-data-from-spans)
and [Braintrust](https://www.braintrust.dev/docs/integrations/developer-tools/mcp)
provide mature observability with dashboards and programmatic access through
APIs, exports or MCP.

Aftersight has a narrower default: ordinary files in the repository, with no
hosted project, credentials or remote query round trips. Those platforms are a
better fit when you need centralized durability, team dashboards or managed
evaluation workflows. See [Why aftersight exists](docs/why.md) for the fuller
comparison.

## Local by default

Aftersight itself makes no network requests and does not upload telemetry.
Payload redaction is enabled by default, and the run folder is added to
`.gitignore` when it is first created.

If the application already has an OpenTelemetry exporter, that exporter may
still send its own spans. Aftersight can run in production, but local disk can
disappear with an ephemeral, replaced or failed host, so it should not be the
only durable production record.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Framework support](docs/frameworks.md)
- [Navigating runs](docs/navigating.md)
- [Python API](docs/reference/api.md)
- [Run folder format](docs/reference/run-folder.md)
- [Architecture](docs/design/architecture.md)

Full documentation: **https://nebulaanish.github.io/aftersight/**
