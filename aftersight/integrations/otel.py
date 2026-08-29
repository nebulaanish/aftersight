"""OpenTelemetry bridge, the reason this works with frameworks it has never
heard of.

A `SpanProcessor`, not a `SpanExporter`. Exporters only see a span when it ends,
and a parent ends after its children, so an exporter-built transcript comes out
inside-out. `on_start` lets container spans open in the right place.

Leaf spans (an LLM call, a tool call) emit both of their events at end, because
that is when the prompt, the completion and the token counts are actually on the
span. They are leaves, so nothing nests underneath them and nothing is misplaced.

Three attribute dialects are read: OpenTelemetry `gen_ai.*` semantic
conventions (pydantic-ai, Traceloop), OpenInference `llm.*` / `openinference.*`
(agno, LangChain, LangGraph), and a generic `input.value` / `output.value`
fallback.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.trace import StatusCode

from aftersight import constants
from aftersight.constants import EventType
from aftersight.utils import announce, log_debug

def _attr(span: ReadableSpan, *keys: str) -> Any:
    attributes = span.attributes or {}
    for key in keys:
        if key in attributes:
            return attributes[key]
    return None


def _indexed(span: ReadableSpan, *templates: str) -> tuple[str | None, int]:
    attributes = span.attributes or {}
    for template in templates:
        parts = []
        for index in range(constants.MAX_INDEXED_MESSAGES):
            value = attributes.get(template.format(i=index))
            if value is None:
                break
            role = attributes.get(template.format(i=index).rsplit(".", 1)[0] + ".role")
            parts.append(f"[{role}]\n{value}" if role else str(value))
        if parts:
            return "\n\n".join(parts), len(parts)
    return None, 0


def _prompt(span: ReadableSpan) -> tuple[str | None, int]:
    text, count = _indexed(span, *constants.PROMPT_TEMPLATES)
    if text:
        return text, count
    single = _attr(span, *constants.PROMPT_ATTRS)
    return (str(single), 1) if single is not None else (None, 0)


def _completion(span: ReadableSpan) -> str | None:
    text, _ = _indexed(span, *constants.COMPLETION_TEMPLATES)
    if text:
        return text
    single = _attr(span, *constants.COMPLETION_ATTRS)
    return str(single) if single is not None else None


def _declared_container(span: ReadableSpan) -> bool:
    """A span that says it is a container, at the moment it starts.

    Most frameworks set their attributes *during* a span, not at creation, so an
    undeclared span is classified at end instead of being guessed at start.
    """
    declared = _attr(span, *constants.SPAN_KIND_ATTRS)
    return str(declared) in constants.CONTAINER_SPAN_KINDS if declared else False


def _kind(span: ReadableSpan) -> str:
    declared = _attr(span, *constants.SPAN_KIND_ATTRS)
    if declared:
        declared = str(declared)
        if declared in constants.LLM_SPAN_KINDS:
            return "llm"
        if declared in constants.TOOL_SPAN_KINDS:
            return "tool"
        if declared in constants.CONTAINER_SPAN_KINDS:
            return "container"
    if _attr(span, *constants.MODEL_ATTRS):
        return "llm"
    if _attr(span, *constants.TOOL_NAME_ATTRS):
        return "tool"
    return "container"


def _tokens(span: ReadableSpan, direction: str) -> int | None:
    names = (constants.INPUT_TOKEN_ATTRS if direction == "input"
             else constants.OUTPUT_TOKEN_ATTRS)
    value = _attr(span, *names)
    return int(value) if value is not None else None


def _duration_ms(span: ReadableSpan) -> int:
    return int(((span.end_time or 0) - (span.start_time or 0)) / 1_000_000)


class TelemetrySpanProcessor(SpanProcessor):
    def __init__(self, run):
        self.run = run
        self._container_seq: dict[int, int] = {}

    def retarget(self, run) -> None:
        self.run = run
        self._container_seq.clear()

    def _parent_seq(self, span: ReadableSpan) -> int | None:
        """An OTel parent if there is one, otherwise the enclosing explicit
        `span()`, so mixing the two APIs still nests correctly."""
        parent = span.parent
        if parent is not None and parent.span_id in self._container_seq:
            return self._container_seq[parent.span_id]
        from aftersight.run import api

        return api._parent.get()

    def on_start(self, span, parent_context=None) -> None:
        try:
            if not _declared_container(span):
                return
            event = self.run.sink.emit(EventType.AGENT_START, span.name,
                                       parent_seq=self._parent_seq(span))
            self._container_seq[span.context.span_id] = event.seq
        except Exception as exc:  # noqa: BLE001
            log_debug(f"on_start failed for {span.name}: {exc}")

    def on_end(self, span: ReadableSpan) -> None:
        try:
            self._emit(span)
        except Exception as exc:  # noqa: BLE001 (never break the traced app)
            log_debug(f"on_end failed for {span.name}: {exc}")

    def _emit(self, span: ReadableSpan) -> None:
        kind = _kind(span)
        parent_seq = self._parent_seq(span)
        failed = span.status is not None and span.status.status_code is StatusCode.ERROR
        message = span.status.description if failed and span.status else None

        if kind == "llm":
            text, messages = _prompt(span)
            call = self.run.sink.emit(
                EventType.LLM_PROMPT, span.name, parent_seq=parent_seq,
                ts=(span.start_time or 0) / 1e9, messages=messages or None,
                tokens_in=_tokens(span, "input"), text=text,
                model=_attr(span, *constants.MODEL_ATTRS))
            self.run.sink.emit(
                EventType.LLM_RESPONSE, span.name, parent_seq=call.seq,
                status="error" if failed else "ok", dur_ms=_duration_ms(span),
                tokens_out=_tokens(span, "output"), text=_completion(span),
                stop_reason=_attr(span, *constants.FINISH_REASON_ATTRS),
                cost_usd=_attr(span, *constants.COST_ATTRS),
                error=message)
        elif kind == "tool":
            name = str(_attr(span, *constants.TOOL_NAME_ATTRS) or span.name)
            call = self.run.sink.emit(
                EventType.TOOL_CALL, name, parent_seq=parent_seq,
                ts=(span.start_time or 0) / 1e9,
                args={"input": _attr(span, *constants.TOOL_ARG_ATTRS)}
                if _attr(span, *constants.TOOL_ARG_ATTRS) else None)
            if failed:
                self.run.sink.emit(EventType.TOOL_ERROR, name, parent_seq=call.seq,
                                   status="error", dur_ms=_duration_ms(span),
                                   error_type=_error_type(span), error=message or "")
            else:
                self.run.sink.emit(EventType.TOOL_RESULT, name, parent_seq=call.seq,
                                   status="ok", dur_ms=_duration_ms(span),
                                   text=_completion(span))
        else:
            seq = self._container_seq.pop(span.context.span_id, None)
            if seq is None:
                # Undeclared at start, container at end: open and close it here so
                # the pair is never dangling.
                seq = self.run.sink.emit(EventType.AGENT_START, span.name,
                                         parent_seq=parent_seq,
                                         ts=(span.start_time or 0) / 1e9).seq
            self.run.sink.emit(EventType.AGENT_END, span.name, parent_seq=parent_seq,
                               status="error" if failed else "ok",
                               dur_ms=_duration_ms(span))
            if failed and seq is not None:
                self.run.sink.emit(EventType.ERROR, span.name, parent_seq=seq,
                                   status="error", error_type=_error_type(span),
                                   error=message or "")

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _error_type(span: ReadableSpan) -> str:
    for event in span.events or ():
        if event.name == "exception":
            return str((event.attributes or {}).get("exception.type", "Error"))
    return "Error"


_PROCESSOR: "TelemetrySpanProcessor | None" = None


def setup_tracing(run) -> None:
    """Attaches to whatever tracer provider the app already has, or installs one.

    Never replaces an existing provider: an app exporting to its own backend
    keeps doing so, and gets a run folder as well.

    A tracer provider cannot have a processor removed, so a second run re-points
    the one already installed instead of stacking another, otherwise every event
    after the second `start()` would be written twice.
    """
    global _PROCESSOR
    if _PROCESSOR is not None:
        _PROCESSOR.retarget(run)
        return
    provider = trace_api.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace_api.set_tracer_provider(provider)
    _PROCESSOR = TelemetrySpanProcessor(run)
    provider.add_span_processor(_PROCESSOR)
    _auto_instrument(provider, run)


def _auto_instrument(provider, run) -> None:
    """Activates OpenInference instrumentors that are already installed. Nothing
    is installed on the user's behalf; frameworks that emit OTel natively
    (pydantic-ai, Traceloop-instrumented apps) need none of this."""
    active = []
    for module_path, class_name, label in constants.INSTRUMENTORS:
        try:
            module = __import__(module_path, fromlist=[class_name])
        except ImportError:
            continue
        try:
            getattr(module, class_name)().instrument(tracer_provider=provider)
            active.append(label)
        except Exception as exc:  # noqa: BLE001
            log_debug(f"could not instrument {label}: {exc}")
    if active and not run.config.quiet:
        announce(f"instrumented {', '.join(active)}")
