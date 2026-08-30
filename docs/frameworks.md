# Frameworks

`aftersight` captures through three paths, in this order of preference:

1. **OpenTelemetry spans.** Anything already emitting them is captured with no
   code change.
2. **stdlib `logging`.** Warnings and exceptions from frameworks that only log.
3. **The explicit API.** For code that does neither.

Most frameworks land in the first path. The rest of this page is per
framework, and each section carries a complete starter you can save to one
file and run. They also live in `examples/starters/` in the repository.

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

Emits OpenTelemetry natively, so `Agent.instrument_all()` is the only extra
line. Use `Agent(..., instrument=True)` instead to record one agent.

```python title="pydantic_ai_starter.py"
--8<-- "examples/starters/pydantic_ai_starter.py"
```

## LangGraph and LangChain

`aftersight.start()` activates any OpenInference instrumentor it finds
installed, and says which ones on stderr:

```
aftersight: instrumented langchain
```

LangChain agents run on LangGraph, so one instrumentor covers both.

```python title="langchain_starter.py"
--8<-- "examples/starters/langchain_starter.py"
```

## agno

```bash
pip install openinference-instrumentation-agno
```

Auto-activated the same way.

## OpenAI Agents SDK

Auto-activated the same way, from
`openinference-instrumentation-openai-agents`.

```python title="openai_agents_starter.py"
--8<-- "examples/starters/openai_agents_starter.py"
```

## Other auto-activated instrumentors

Install the one you need and `start()` will find it:

| Framework | Package |
|---|---|
| CrewAI | `openinference-instrumentation-crewai` |
| LlamaIndex | `openinference-instrumentation-llama-index` |
| smolagents | `openinference-instrumentation-smolagents` |

Nothing is installed on your behalf. Only packages already present are switched
on.

## Traceloop and OpenLLMetry

These emit `gen_ai.*` semantic convention attributes, which `aftersight` reads
directly. No instrumentor needed on our side, just start both.

## Claude Agent SDK

The SDK does not emit in-process OpenTelemetry spans today, so use the
explicit API. A thin wrapper is enough, and the SDK hands back its own cost
and turn count to put on the span.

```python title="claude_agent_sdk_starter.py"
--8<-- "examples/starters/claude_agent_sdk_starter.py"
```

If a future version does emit `gen_ai.*` spans, they are picked up
automatically and this wrapper becomes redundant.

## OpenHands

OpenHands logs heavily and the logging bridge captures WARNING and above as
`log` and `error` events, which covers failure diagnosis. Lower the threshold
to `logging.INFO` for the full narrative, at the cost of volume, and wrap the
loop you care about to give the trace some structure.

```python title="openhands_starter.py"
--8<-- "examples/starters/openhands_starter.py"
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
