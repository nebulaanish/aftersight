from __future__ import annotations

import logging
import re
import sys
from typing import Any

from aftersight.constants import REDACTION_MASK, SECRET_PATTERNS

_logger = logging.getLogger("aftersight")
_compiled = [re.compile(pattern) for pattern in SECRET_PATTERNS]


def log_debug(msg: str) -> None:
    _logger.debug(msg)


def log_error(msg: str) -> None:
    _logger.error(msg)


def announce(msg: str) -> None:
    print(f"aftersight: {msg}", file=sys.stderr)


# Run folders live inside the user's repo, so a leaked key in a prompt is a key
# on disk.


def redact_text(text: str) -> str:
    for pattern in _compiled:
        if pattern.groups:
            text = pattern.sub(
                lambda m: m.group(0).replace(m.group(1), REDACTION_MASK), text)
        else:
            text = pattern.sub(REDACTION_MASK, text)
    return text


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    return f"{nbytes / 1024 / 1024:.1f} MB"
