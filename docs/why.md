# Why aftersight exists

Agent systems repeat their failures. The same tool times out, the same prompt
overflows, and the same retry path burns time or money. Fixing the system
requires evidence that survives the run.

Aftersight keeps that evidence close to the code and in a form the next reader
can use directly.

## A different reader

Observability has traditionally been designed for a person looking at a
dashboard. A coding agent works differently. It searches files, follows
references, runs shell commands and edits the repository where it found the
problem.

Existing telemetry can be exposed to that agent through APIs, exports or MCP.
Aftersight makes agent access the default instead: the trace is already a set of
ordinary files in the repository.

## Why repository files

Local files remove setup and access layers from the debugging loop:

```text
run -> files -> diagnosis -> code change -> run
```

The agent can orient in `outline.md`, read full payloads in `agent.logs` and
aggregate events from `trace.jsonl`. Stable `#seq` anchors connect those
views. Humans can read the same files, while scripts and frontends can consume
the JSON and JSONL projections.

Research supports the broader design choice. [SWE-agent](https://arxiv.org/abs/2405.15793)
shows that repository-navigation interfaces materially affect coding-agent
performance. [PILOT](https://openreview.net/pdf?id=urqcdb6ECn) evaluates an
RL-trained agent that explores through terminal commands including `rg`,
`find` and `cat`. [CodeGrep](https://arxiv.org/abs/2608.05886) trains a
retrieval agent to issue grep, glob and file-reading calls.

This does not prove that proprietary coding agents are trained specifically on
`rg`. It does show that file and terminal exploration are established agent
workflows worth designing for.

## What building agent systems taught me

Aftersight is a byproduct of building multiple agentic systems and improving
their harnesses. Several telemetry choices kept proving useful:

- preserve complete inputs and outputs instead of silently truncating them;
- give every event a stable anchor;
- keep a short orientation view beside the complete transcript;
- make cross-run failures searchable without a database;
- append resumed attempts instead of overwriting the failed evidence.

Aftersight packages those repeated lessons without the application-specific
parts of the systems they came from.

## Compared with hosted observability

[LangSmith](https://docs.langchain.com/langsmith/langsmith-mcp-server) records
and analyzes traces through a service and also offers an MCP server for model
access. [Langfuse](https://langfuse.com/docs/api-and-data-platform/features/observations-api)
provides dashboards and observation APIs, with cloud and self-hosted options.
[Phoenix](https://arize.com/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/extract-data-from-spans)
supports visual trace analysis and programmatic span export.
[Braintrust](https://www.braintrust.dev/docs/integrations/developer-tools/mcp)
combines observability and evaluation workflows with API and MCP access for
coding tools.

Those products solve broader collaboration, evaluation and production
observability problems. Aftersight is intentionally smaller. Its primary
interface is the local filesystem, so exploration requires no hosted project,
credentials, query API or remote MCP call.

The difference is a default, not an exclusive capability. Choose a hosted or
self-hosted platform when you need centralized durability, shared dashboards,
access controls or managed evaluation. Use aftersight when the shortest path
from a run to the coding agent working on it should stay inside the repository.
The two can coexist through OpenTelemetry.

## Local-first tradeoffs

Aftersight itself makes no network requests and uploads nothing. The run folder
is git-ignored, and common secret shapes are redacted before writing.

Local storage also has a clear limit. A run can disappear with an ephemeral,
replaced or failed host. Aftersight can be used in production, but it should not
be the only durable production record unless the filesystem itself is durable.
An application's existing OpenTelemetry exporter may continue sending the same
spans elsewhere.

## What aftersight is not

Aftersight is not a dashboard. It is not an evaluation framework, and it does
not diagnose or modify an agent by itself. It records what happened in a shape
that lets an agent, person or client investigate and act on the evidence.
