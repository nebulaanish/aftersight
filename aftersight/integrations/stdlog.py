"""stdlib `logging` bridge.

Frameworks that emit no spans still log, and a warning or an exception is
exactly the thing worth having in the trace. WARNING and above by default,
because capturing INFO from a whole dependency tree would bury the run.
"""

from __future__ import annotations

import logging

from aftersight.constants import EventType


class TelemetryHandler(logging.Handler):
    def __init__(self, run, level: int = logging.WARNING):
        super().__init__(level)
        self.run = run

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("aftersight"):
            return
        if self.run.finalized:
            return
        payload = {"level": record.levelname, "logger": record.name,
                   "message": record.getMessage()}
        if record.exc_info:
            payload["text"] = self.format(record)
            self.run.sink.emit(EventType.ERROR, record.name, status="error",
                               error_type=record.exc_info[0].__name__,
                               error=str(record.exc_info[1]), text=payload["text"])
            return
        self.run.sink.emit(EventType.LOG, record.name,
                           status=record.levelname.lower(), **payload)


_HANDLER: "TelemetryHandler | None" = None


def setup_logging(run, level: int = logging.WARNING) -> "TelemetryHandler":
    """One handler per process, re-pointed on a second run rather than stacked."""
    global _HANDLER
    if _HANDLER is not None:
        _HANDLER.run = run
        _HANDLER.setLevel(level)
        return _HANDLER
    _HANDLER = TelemetryHandler(run, level)
    logging.getLogger().addHandler(_HANDLER)
    return _HANDLER
