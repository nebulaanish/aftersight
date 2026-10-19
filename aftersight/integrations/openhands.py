"""OpenHands tool calls, recorded through its conversation callbacks:

    Conversation(agent=agent, workspace=..., callbacks=[record_tools])

OpenHands only emits tool spans through Laminar, which exports off the machine.
Events are recognised by their fields, so OpenHands is never imported here.
"""

from __future__ import annotations

from typing import Any

from aftersight.run import api


class ToolError(Exception):
    pass


_open: dict[str, tuple[Any, Any]] = {}


def record_tools(event: Any) -> None:
    call_id = getattr(event, "tool_call_id", None)
    if call_id is None:
        return
    if hasattr(event, "action"):
        action = event.action
        args = action.model_dump(exclude_none=True) if hasattr(action, "model_dump") else action
        span = api.span(event.tool_name, kind="tool", args=args)
        _open[call_id] = (span, span.__enter__())
        return
    span, handle = _open.pop(call_id, (None, None))
    if span is None:
        return
    observation = getattr(event, "observation", None)
    error = getattr(event, "error", None)
    if observation is not None and getattr(observation, "is_error", False):
        error = observation.text
    elif observation is None and error is None:
        # UserRejectObservation: the tool never ran.
        error = f"rejected: {getattr(event, 'rejection_reason', '')}"
    if error is None:
        handle.output = observation.text
        span.__exit__(None, None, None)
    else:
        span.__exit__(ToolError, ToolError(error), None)
