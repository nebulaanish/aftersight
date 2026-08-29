"""The read side and the root directory itself.

Pointers (`latest`, `sessions/`) live outside `runs/` so that a `runs/*/...`
glob cannot count the same run twice through a symlink.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from aftersight import constants
from aftersight.utils import log_error

def runs_dir(root: Path) -> Path:
    return Path(root) / constants.RUNS_DIR


def ensure_root(root: Path) -> Path:
    """Creates the telemetry root on first use. No `init` command to discover."""
    root = Path(root)
    runs_dir(root).mkdir(parents=True, exist_ok=True)
    (root / constants.SESSIONS_DIR).mkdir(exist_ok=True)
    navigate = root / constants.NAVIGATE_FILE
    if not navigate.exists():
        source = Path(__file__).resolve().parent.parent / "assets" / constants.NAVIGATE_FILE
        navigate.write_text(source.read_text())
    _ensure_gitignored(root)
    return root


def _ensure_gitignored(root: Path) -> None:
    """A run folder inside a repo must never be committed by accident.

    Only a dotted root inside the repo is ignored. A root outside the repo has
    nothing to do with it, and a visibly-named one was chosen deliberately:
    this package's own example fixture is a run folder that belongs in git.
    """
    try:
        repo = Path.cwd().resolve()
        if not (repo / ".git").exists() or not root.name.startswith("."):
            return
        try:
            entry = f"{root.resolve().relative_to(repo)}/"
        except ValueError:
            return  # outside the repo
        gitignore = repo / ".gitignore"
        existing = gitignore.read_text() if gitignore.exists() else ""
        if entry in existing.split():
            return
        mark = "" if constants.GITIGNORE_MARK in existing else f"\n{constants.GITIGNORE_MARK}"
        with gitignore.open("a") as handle:
            handle.write(f"{mark}\n{entry}\n")
    except OSError as exc:  # noqa: BLE001 (a read-only checkout is not our problem)
        log_error(f"could not update .gitignore: {exc}")


def resolve_session(root: Path, session_id: str) -> Path | None:
    link = Path(root) / constants.SESSIONS_DIR / session_id
    if link.is_symlink() or link.exists():
        target = link.resolve()
        if target.is_dir():
            return target
    return None


def point(link: Path, target: Path) -> None:
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        # Relative, so a pointer survives the root being moved or committed:
        # an absolute target would bake in whoever's machine wrote it.
        link.symlink_to(os.path.relpath(Path(target).resolve(), link.parent.resolve()))
    except OSError as exc:  # noqa: BLE001 (Windows without developer mode)
        log_error(f"could not link {link}: {exc}")


def read_meta(run_dir: Path) -> dict:
    path = Path(run_dir) / constants.META_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def write_meta(run_dir: Path, meta: dict) -> None:
    (Path(run_dir) / constants.META_FILE).write_text(json.dumps(meta, indent=2) + "\n")


def update_index(root: Path, summary: dict) -> None:
    path = Path(root) / constants.INDEX_FILE
    errors = summary.get("errors") or []
    row = {
        "run_id": summary.get("run_id"),
        "session_id": summary.get("session_id"),
        "started_at": summary.get("started_at"),
        "status": summary.get("status"),
        "active_sec": summary.get("active_sec"),
        "cost_usd": summary.get("cost", {}).get("cost_usd"),
        "llm_calls": summary.get("llm_calls"),
        "tool_calls": summary.get("tool_calls"),
        "errors": len(errors),
        "framework": summary.get("framework"),
        "model": summary.get("model"),
        "last_error": (f"{errors[-1]['type']}: {errors[-1]['message']}" if errors else None),
    }
    kept = []
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and f'"run_id": "{row["run_id"]}"' not in line:
                kept.append(line)
    kept.append(json.dumps(row))
    path.write_text("\n".join(kept) + "\n")


def prune(root: Path, keep: int) -> None:
    """Bounded history. Unbounded run folders is the reason people turn
    telemetry off."""
    if keep <= 0:
        return
    directories = sorted(p for p in runs_dir(root).iterdir() if p.is_dir())
    for stale in directories[:-keep]:
        try:
            shutil.rmtree(stale)
        except OSError as exc:  # noqa: BLE001
            log_error(f"could not prune {stale}: {exc}")
    sessions = Path(root) / constants.SESSIONS_DIR
    for link in sessions.iterdir() if sessions.is_dir() else []:
        if link.is_symlink() and not link.resolve().exists():
            link.unlink()
