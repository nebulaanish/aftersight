from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

from aftersight import constants


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    root: Path = Path(constants.DEFAULT_ROOT)
    keep_runs: int = constants.DEFAULT_KEEP_RUNS
    blob_max_bytes: int = constants.DEFAULT_BLOB_MAX_BYTES
    blob_preview_lines: int = constants.DEFAULT_BLOB_PREVIEW_LINES
    capture_otel: bool = True
    capture_logging: bool = True
    log_level: int = logging.WARNING
    redact: bool = True
    quiet: bool = False


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in constants.TRUTHY:
        return True
    if lowered in constants.FALSY:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def load(**overrides) -> Config:
    """Defaults, then environment, then explicit `start()` arguments."""
    cfg = Config(
        enabled=_env_bool(constants.ENV_ENABLED, True),
        root=Path(os.environ.get(constants.ENV_ROOT, constants.DEFAULT_ROOT)),
        keep_runs=_env_int(constants.ENV_KEEP_RUNS, constants.DEFAULT_KEEP_RUNS),
        blob_max_bytes=_env_int(constants.ENV_BLOB_MAX, constants.DEFAULT_BLOB_MAX_BYTES),
        capture_otel=_env_bool(constants.ENV_OTEL, True),
        capture_logging=_env_bool(constants.ENV_LOGGING, True),
        redact=_env_bool(constants.ENV_REDACT, True),
        quiet=_env_bool(constants.ENV_QUIET, False),
    )
    known = {f for f in Config.__dataclass_fields__}
    clean = {k: v for k, v in overrides.items() if k in known and v is not None}
    if "root" in clean:
        clean["root"] = Path(clean["root"])
    return replace(cfg, **clean) if clean else cfg
