"""Telemetry that a coding agent can navigate.

    import aftersight
    aftersight.start()

Or, with no code change at all:

    aftersight run python my_agent.py
"""

from aftersight.run.api import (
    artifact_dir,
    current,
    log,
    span,
    start,
    trace,
)

__all__ = ["start", "span", "trace", "log", "current", "artifact_dir"]
__version__ = "0.1.0"
