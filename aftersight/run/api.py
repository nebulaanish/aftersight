"""The public surface. Three things to learn, and only the first is required.

    aftersight.start()                       # capture everything
    with aftersight.span("web_search", kind="tool") as s: ...
    aftersight.log("cache miss", key=key)
"""

from __future__ import annotations

import atexit
import contextvars
import functools
import inspect
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from aftersight import config as config_module
from aftersight.constants import EventType
from aftersight.run.run import Run
from aftersight.utils import log_error

_run: contextvars.ContextVar["Run | None"] = contextvars.ContextVar(
    "aftersight_run", default=None)
_parent: contextvars.ContextVar["int | None"] = contextvars.ContextVar(
    "aftersight_parent", default=None)


class _Disabled:
    """What `start()` returns when AFTERSIGHT=0. Nothing is created on disk."""

    finalized = True
    artifacts = Path(".")

    def finalize(self, status: str | None = None) -> dict:
        return {}

    def __enter__(self) -> "_Disabled":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def current() -> Run | None:
    return _run.get()


def start(session_id: str | None = None, *, tags: tuple[str, ...] = (), **kwargs: Any):
    """Begin recording. Safe to call twice, the second call returns the first run.

    Use it bare for a process-scoped run finalised at exit, or as a context
    manager to scope it yourself. Config fields (`root`, `keep_runs`, `quiet`, …)
    and free-form metadata (`framework`, `model`, `task`, …) both go here.
    """
    active = _run.get()
    if active is not None and not active.finalized:
        return active

    known = set(config_module.Config.__dataclass_fields__)
    cfg = config_module.load(**{k: v for k, v in kwargs.items() if k in known})
    if not cfg.enabled:
        return _Disabled()

    meta = {k: v for k, v in kwargs.items() if k not in known}
    try:
        run = Run(cfg, session_id=session_id, tags=tags, **meta)
    except Exception as exc:  # noqa: BLE001 (a broken run folder must not stop the agent)
        log_error(f"could not start telemetry: {exc}")
        return _Disabled()

    _run.set(run)
    _install(run, cfg)
    atexit.register(run.finalize)
    _hook_excepthook(run)
    return run


def _install(run: Run, cfg) -> None:
    if cfg.capture_otel:
        from aftersight.integrations import otel
        otel.setup_tracing(run)
    if cfg.capture_logging:
        from aftersight.integrations import stdlog
        stdlog.setup_logging(run, cfg.log_level)


def _hook_excepthook(run: Run) -> None:
    """An unhandled exception is the failure most worth having in the trace."""
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        if not run.finalized and not getattr(exc, "_aftersight_logged", False):
            run.sink.emit(EventType.ERROR, exc_type.__name__, status="error",
                          error_type=exc_type.__name__, error=str(exc))
        previous(exc_type, exc, tb)

    sys.excepthook = hook


@contextmanager
def span(name: str, kind: str = "agent", **fields: Any):
    """A step worth seeing in the transcript. `kind` is "agent" or "tool"."""
    run = _run.get()
    if run is None or run.finalized:
        run = start()
        if isinstance(run, _Disabled):
            yield _NullSpan()
            return
    tool = kind == "tool"
    opened = run.sink.emit(EventType.TOOL_CALL if tool else EventType.AGENT_START,
                           name, parent_seq=_parent.get(), **fields)
    handle = _Span(run, opened.seq, name, tool)
    token = _parent.set(opened.seq)
    began = time.time()
    try:
        yield handle
    except Exception as exc:
        exc._aftersight_logged = True  # the excepthook must not log it again
        run.sink.emit(EventType.TOOL_ERROR if tool else EventType.ERROR, name,
                      parent_seq=opened.seq, status="error",
                      dur_ms=int((time.time() - began) * 1000),
                      error_type=type(exc).__name__, error=str(exc))
        if not tool:
            run.sink.emit(EventType.AGENT_END, name, parent_seq=_parent.get(),
                          status="error", dur_ms=int((time.time() - began) * 1000))
        raise
    else:
        run.sink.emit(EventType.TOOL_RESULT if tool else EventType.AGENT_END, name,
                      parent_seq=opened.seq if tool else None, status="ok",
                      dur_ms=int((time.time() - began) * 1000), **handle.fields)
    finally:
        _parent.reset(token)


class _Span:
    def __init__(self, run: Run, seq: int, name: str, tool: bool):
        self.run, self.seq, self.name, self.tool = run, seq, name, tool
        self.fields: dict[str, Any] = {}

    def set(self, **fields: Any) -> None:
        self.fields.update(fields)

    @property
    def output(self) -> Any:
        return self.fields.get("text")

    @output.setter
    def output(self, value: Any) -> None:
        self.fields["text"] = value if isinstance(value, str) else repr(value)


class _NullSpan(_Span):
    def __init__(self):
        self.fields = {}

    def set(self, **fields: Any) -> None:
        pass


def trace(func=None, *, kind: str = "tool", name: str | None = None):
    """Decorator form. Works on sync and async functions.

        @aftersight.trace
        def web_search(query): ...
    """
    def wrap(fn):
        label = name or fn.__name__
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrapper(*args, **kwargs):
                with span(label, kind=kind, args=_args(fn, args, kwargs)) as handle:
                    result = await fn(*args, **kwargs)
                    handle.output = result
                    return result
            return awrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with span(label, kind=kind, args=_args(fn, args, kwargs)) as handle:
                result = fn(*args, **kwargs)
                handle.output = result
                return result
        return wrapper

    return wrap if func is None else wrap(func)


def _args(fn, args, kwargs) -> dict:
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs)
        return {k: v for k, v in bound.arguments.items() if k != "self"}
    except (TypeError, ValueError):
        return dict(kwargs)


def log(message: str, level: str = "INFO", **fields: Any) -> None:
    run = _run.get()
    if run is None or run.finalized:
        return
    run.sink.emit(EventType.LOG, fields.pop("logger", "app"), status=level.lower(),
                  parent_seq=_parent.get(), level=level.upper(), message=message, **fields)


def artifact_dir() -> Path:
    """Where to put files worth keeping alongside the trace."""
    run = _run.get()
    return run.artifacts if run is not None else Path(".")
