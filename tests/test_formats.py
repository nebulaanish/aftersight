"""Format invariants, asserted against real output.

Run directly (`python tests/test_formats.py`) or under pytest. The invariants
here are the ones the NAVIGATE.md recipes depend on, break one and a coding
agent silently gets wrong answers, which is worse than a crash.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aftersight
from aftersight.run import api
from aftersight.writers.trace import read_events

SECRET = "sk-livekeyABCDEFGHIJKLMNOP"


def _fresh(tmp: Path, **kwargs):
    api._run.set(None)
    return aftersight.start(root=tmp, quiet=True, **kwargs)


def _produce(tmp: Path, session: str | None = None) -> Path:
    run = _fresh(tmp, session_id=session, framework="demo", model="test-model",
                 task="find the bug")
    with aftersight.span("planner"):
        aftersight.log("thinking", token=SECRET)
        with aftersight.span("web_search", kind="tool", args={"q": "x"}) as s:
            s.output = "3 hits"
        try:
            with aftersight.span("run_python", kind="tool", args={"code": "boom()"}):
                raise TimeoutError("exceeded 30s wall clock")
        except TimeoutError:
            pass
    with aftersight.span("writer") as s:
        s.set(text="a very long payload\n" * 2000)
    run.finalize()
    return Path(run.dir)


def test_anchors_agree_across_projections():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _produce(Path(tmp))
        logs = (run_dir / "agent.logs").read_text()
        events = list(read_events(run_dir))

        seqs = [e.seq for e in events]
        assert seqs == list(range(1, len(seqs) + 1)), "sequence must be contiguous"

        for event in events:
            assert re.search(rf"^#{event.seq:04d} ", logs, re.M), \
                f"{event.anchor} missing from agent.logs"

        outline = (run_dir / "outline.md").read_text()
        for anchor in re.findall(r"#(\d{4})", outline):
            assert int(anchor) in seqs, f"outline references unknown #{anchor}"


def test_frames_repeat_their_anchor():
    with tempfile.TemporaryDirectory() as tmp:
        logs = (_produce(Path(tmp)) / "agent.logs").read_text().splitlines()
        opens = [i for i, line in enumerate(logs) if line.startswith("┌")]
        assert opens, "expected at least one framed payload"
        for index in opens:
            closing = next(line for line in logs[index:] if line.startswith("└"))
            assert "end · " in closing or "full text:" in closing


def test_large_payload_spills_to_a_greppable_blob():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _produce(Path(tmp))
        blobs = list((run_dir / "blobs").glob("*.txt"))
        assert blobs, "oversized payload should have spilled"
        assert "a very long payload" in blobs[0].read_text(), "blob must be plain text"
        assert f"blobs/{blobs[0].name}" in (run_dir / "agent.logs").read_text()


def test_failures_are_counted_by_error_type_not_status():
    """agent.end also carries status "error"; NAVIGATE.md's recipes rely on this."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _produce(Path(tmp))
        events = list(read_events(run_dir))
        by_type = [e for e in events if e.payload.get("error_type")]
        assert len(by_type) == 1, "exactly one real failure was produced"
        summary = json.loads((run_dir / "analytics.json").read_text())
        assert len(summary["errors"]) == 1


def test_run_end_carries_the_run_total():
    """Anything ranking slow steps must exclude run.*, assert the reason exists."""
    with tempfile.TemporaryDirectory() as tmp:
        events = list(read_events(_produce(Path(tmp))))
        end = events[-1]
        assert end.type == "run.end"
        assert end.dur_ms is not None


def test_resume_continues_the_same_folder_and_sequence():
    with tempfile.TemporaryDirectory() as tmp:
        first = _produce(Path(tmp), session="sess-1")
        last_seq = list(read_events(first))[-1].seq
        second = _produce(Path(tmp), session="sess-1")
        assert first == second, "a resumed session reuses its run folder"
        events = list(read_events(second))
        assert events[last_seq].seq == last_seq + 1, "sequence continues across attempts"
        assert {e.attempt for e in events} == {1, 2}
        assert "==== attempt 2" in (second / "agent.logs").read_text()


def test_pointers_stay_out_of_the_runs_glob():
    with tempfile.TemporaryDirectory() as tmp:
        _produce(Path(tmp))
        root = Path(tmp)
        traces = list(root.glob("runs/*/trace.jsonl"))
        assert len(traces) == 1, "runs/* must not double-count through latest/"
        assert (root / "latest").is_symlink()
        assert not os.path.isabs(os.readlink(root / "latest")), "pointers stay relative"


def test_secrets_are_redacted():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _produce(Path(tmp))
        for path in run_dir.rglob("*"):
            if path.is_file():
                assert SECRET not in path.read_text(), f"secret leaked into {path.name}"


def test_disabled_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AFTERSIGHT"] = "0"
        try:
            api._run.set(None)
            run = aftersight.start(root=Path(tmp) / "off")
            with aftersight.span("planner"):
                aftersight.log("hello")
            run.finalize()
            assert not (Path(tmp) / "off").exists()
        finally:
            del os.environ["AFTERSIGHT"]


def test_zero_code_change_wrapper_records():
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "plain.py"
        script.write_text(
            "from opentelemetry import trace\n"
            "t = trace.get_tracer('x')\n"
            "with t.start_as_current_span('agent', attributes={'openinference.span.kind': 'AGENT'}):\n"
            "    pass\n")
        root = Path(tmp) / "runs-root"
        result = subprocess.run(
            [sys.executable, "-m", "aftersight.cli", "run", "--root", str(root),
             sys.executable, str(script)],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
                 "AFTERSIGHT_QUIET": "1"})
        assert result.returncode == 0, result.stderr
        traces = list(root.glob("runs/*/trace.jsonl"))
        assert traces, f"wrapper produced no run: {result.stderr}"
        types = {e.type for e in read_events(traces[0].parent)}
        assert {"run.start", "agent.start", "agent.end", "run.end"} <= types


def test_gitignore_is_only_touched_for_a_dotted_root_inside_the_repo():
    """A stray root must not append a line to the project's .gitignore."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / ".git").mkdir(parents=True)
        gitignore = repo / ".gitignore"
        gitignore.write_text("*.pyc\n")
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            _fresh(Path(tmp) / "outside").finalize()          # outside the repo
            assert gitignore.read_text() == "*.pyc\n"
            _fresh(repo / "visible_runs").finalize()          # deliberately named
            assert gitignore.read_text() == "*.pyc\n"
            _fresh(repo / ".runs").finalize()                 # the default
            assert ".runs/" in gitignore.read_text().split()
            _fresh(repo / ".runs").finalize()                 # not appended twice
            assert gitignore.read_text().split().count(".runs/") == 1
        finally:
            os.chdir(cwd)


def test_starters_compile_and_use_the_public_api():
    """A starter is copied out of the docs and run, so a broken one is a bad
    first impression rather than a caught error."""
    starters = sorted((Path(__file__).resolve().parent.parent
                       / "examples" / "starters").glob("*.py"))
    assert starters, "the docs snippet every file in examples/starters"
    for path in starters:
        source = path.read_text()
        compile(source, str(path), "exec")
        assert "aftersight.start(" in source, f"{path.name} never starts a run"


def test_a_named_framework_without_its_instrumentor_says_so():
    """An empty run reads as a broken tool, so the missing package is named."""
    from aftersight.integrations import otel

    class _Run:
        framework = "ghost"
        config = type("C", (), {"quiet": True})()

    said, original = [], otel.announce
    otel.constants.INSTRUMENTORS = [
        ("openinference.instrumentation.no_such_thing", "X", "ghost")]
    otel.announce = said.append
    try:
        otel._auto_instrument(None, _Run())
    finally:
        otel.announce = original
        importlib.reload(otel.constants)

    assert said, "a missing instrumentor was not reported"
    assert 'pip install "aftersight[ghost]"' in said[0], said


def test_every_instrumentor_has_the_extra_its_warning_names():
    """The warning tells you to install `aftersight[<framework>]`, so every
    framework in the table needs that extra, wired to the right distribution."""
    from aftersight import constants

    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    for module_path, _, label in constants.INSTRUMENTORS:
        distribution = module_path.replace(".", "-").replace("_", "-")
        assert f'{label} = ["{distribution}"]' in pyproject, (
            f"pyproject has no [{label}] extra installing {distribution}")


def demo() -> None:
    for name, case in sorted(globals().items()):
        if name.startswith("test_"):
            case()
            print(f"ok  {name}")
    print("\nall format invariants hold")


if __name__ == "__main__":
    demo()
