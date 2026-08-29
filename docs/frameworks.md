# Frameworks

`aftersight` captures through three paths, in this order of preference:

1. **OpenTelemetry spans.** Anything already emitting them is captured with no
   code change.
2. **stdlib `logging`.** Warnings and exceptions from frameworks that only log.
3. **The explicit API.** For code that does neither.

Most frameworks land in the first path. The rest of this page is per framework.

## Check what you are already getting

Run once, then count the event types that landed:

```bash
aftersight run python my_agent.py
jq -r '.type' .runs/latest/trace.jsonl | sort | uniq -c
```

If you see only `run.start` and `run.end`, nothing was captured automatically
and you want an instrumentor or the explicit API. If you see `llm.prompt`,
`tool.call` and `agent.start`, you are done.

## pydantic-ai

Emits OpenTelemetry natively. Nothing extra to install.

```python
import aftersight
from pydantic_ai import Agent

aftersight.start()
Agent.instrument_all()          # or Agent(..., instrument=True) per agent
```

## LangGraph and LangChain

```bash
pip install openinference-instrumentation-langchain
```

That is all. `aftersight.start()` activates any OpenInference instrumentor it
finds installed, and says which ones on stderr:

```
aftersight: instrumented langchain
```

## agno

```bash
pip install openinference-instrumentation-agno
```

Auto-activated the same way.

## Other auto-activated instrumentors

Install the one you need and `start()` will find it:

| Framework | Package |
|---|---|
| CrewAI | `openinference-instrumentation-crewai` |
| LlamaIndex | `openinference-instrumentation-llama-index` |
| OpenAI Agents SDK | `openinference-instrumentation-openai-agents` |
| smolagents | `openinference-instrumentation-smolagents` |

Nothing is installed on your behalf. Only packages already present are switched
on.

## Traceloop and OpenLLMetry

These emit `gen_ai.*` semantic convention attributes, which `aftersight` reads
directly. No instrumentor needed on our side, just start both.

## Claude Agent SDK

The SDK does not emit in-process OpenTelemetry spans today, so use the explicit
API. A thin wrapper is usually enough:

```python
import aftersight
from claude_agent_sdk import query

aftersight.start(framework="claude-agent-sdk")

async def ask(prompt: str) -> str:
    with aftersight.span("claude", kind="agent") as s:
        chunks = [m async for m in query(prompt=prompt)]
        s.set(text="".join(str(c) for c in chunks), messages=len(chunks))
        return s.output
```

If a future version does emit `gen_ai.*` spans, they are picked up
automatically and this wrapper becomes redundant.

## OpenHands

OpenHands logs heavily and the logging bridge captures WARNING and above as
`log` and `error` events, which covers failure diagnosis. For structure, wrap
the loop you care about:

```python
with aftersight.span("openhands", kind="agent"):
    ...
```

Lower the threshold if you want the full narrative, at the cost of volume:

```python
import logging
aftersight.start(log_level=logging.INFO)
```

## Anything else

The explicit API works with any code:

```python
import aftersight

aftersight.start(framework="my-harness", model="claude-sonnet-5")

with aftersight.span("planner"):
    with aftersight.span("search", kind="tool", args={"q": q}) as s:
        s.output = search(q)
```

See the [Python API](reference/api.md) for the full surface.

## Coexisting with an existing OpenTelemetry setup

`aftersight` never replaces a tracer provider. If your app already exports to
Logfire, Phoenix, Langfuse or an OTLP collector, it keeps doing so and gets a
run folder as well. If no provider is configured, one is installed.

Because a tracer provider cannot have a processor removed, calling `start()` a
second time in one process re-points the processor that is already installed
rather than adding another. Without that, every event after the second call
would be written twice.

## Attribute dialects

Three are read, which is why frameworks this package has never heard of tend to
work:

| Dialect | Prompt | Completion | Tokens | Model |
|---|---|---|---|---|
| OTel `gen_ai` | `gen_ai.prompt`, `gen_ai.prompt.{i}.content` | `gen_ai.completion`, `gen_ai.completion.{i}.content` | `gen_ai.usage.input_tokens` | `gen_ai.request.model` |
| OpenInference | `llm.input_messages.{i}.message.content` | `llm.output_messages.{i}.message.content` | `llm.token_count.prompt` | `llm.model_name` |
| Generic | `input.value` | `output.value` | | |

Span kind comes from `openinference.span.kind`, `gen_ai.operation.name` or
`traceloop.span.kind`, and falls back to inspecting which attributes are
present. Cost is read from `gen_ai.usage.cost` or `llm.cost.total` when the
framework reports it.
