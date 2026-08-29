"""Produces examples/telemetry_root/, the worked run used as the format spec.

Doubles as example code. Two processes share one session id: the first crashes
mid-executor, the second resumes into the same folder and fails properly.

    python examples/generate.py
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

from opentelemetry import trace

import aftersight

ROOT = Path(__file__).resolve().parent / "telemetry_root"
SESSION = "sess_kaggle_eda_7c"
TASK = ("whats the dimensionality of the spontaneous recordings, and can you "
        "plot the variance explained curve?")

tracer = trace.get_tracer("neuro-pipeline")


def corpus() -> str:
    """A prompt big enough to spill to blobs/, which is the point of it."""
    random.seed(7)
    kinds = ["spont", "drifting_gratings", "natural_scenes", "sparse_noise"]
    lines = ["You are the planner. Below is the laboratory's full corpus index.", ""]
    for i in range(1400):
        lines.append(f"## {random.choice(kinds)}_{2024 + i % 3}_{i:04d}")
        lines.append(f"  spikes.npy  ({random.randint(800, 12000)}, "
                     f"{random.randint(4000, 22000)})  int16")
    return "\n".join(lines)


def llm(name: str, prompt: str, completion: str, tokens_in: int, tokens_out: int,
        cost: float, stop: str = "end_turn") -> None:
    with tracer.start_as_current_span(name, attributes={"gen_ai.operation.name": "chat"}) as s:
        s.set_attribute("gen_ai.request.model", "claude-sonnet-5")
        s.set_attribute("gen_ai.prompt.0.role", "system")
        s.set_attribute("gen_ai.prompt.0.content", prompt)
        s.set_attribute("gen_ai.completion.0.content", completion)
        s.set_attribute("gen_ai.usage.input_tokens", tokens_in)
        s.set_attribute("gen_ai.usage.output_tokens", tokens_out)
        s.set_attribute("gen_ai.usage.cost", cost)
        s.set_attribute("gen_ai.response.finish_reasons", stop)


def attempt_one() -> None:
    aftersight.start(session_id=SESSION, root=ROOT, framework="langgraph",
                          framework_version="0.6.4", model="claude-sonnet-5", task=TASK,
                          tags=("eda", "stringer"), quiet=True)
    with aftersight.span("triage") as triage:
        llm("triage", "You are the front door of a data-analysis pipeline.\n\n"
            "[user]\n" + TASK,
            '{"decision": "work", "reason": "asks for a dataset property and a plot"}',
            812, 386, 0.0005)
        triage.set(cost_usd=0.0005)

    with aftersight.span("planner") as planner:
        llm("planner", corpus(), "Plan:\n1. Load spikes.npy\n2. PCA, 200 components\n"
            "3. Plot cumulative variance explained.", 69340, 1204, 0.0121, stop="tool_use")
        with aftersight.span("web_search", kind="tool",
                                  args={"query": "stringer spontaneous preprocessing"}) as s:
            s.set(results=12)
        try:
            with aftersight.span("read_file", kind="tool", args={"path": "/etc/hosts"}):
                raise PermissionError("[Errno 13] Permission denied: '/etc/hosts'")
        except PermissionError:
            pass
        planner.set(cost_usd=0.0121)

    with aftersight.span("executor"):
        try:
            with aftersight.span("run_python", kind="tool",
                                      args={"code": "X = np.load('spikes.npy'); PCA(200).fit(X)"}):
                raise TimeoutError("exceeded 30s wall clock")
        except TimeoutError:
            pass
        os._exit(1)  # the crash: no run.end, so the next attempt marks it


def attempt_two() -> None:
    aftersight.start(session_id=SESSION, root=ROOT, quiet=True)
    with aftersight.span("executor") as executor:
        llm("executor", "The previous attempt timed out at peak 3812 MiB. Chunk the load.",
            "Loading with mmap_mode='r' to avoid materialising the array.",
            2841, 892, 0.0104, stop="tool_use")
        try:
            with aftersight.span("run_python", kind="tool",
                                      args={"code": "np.load('spikes.npy', mmap_mode='r')"}):
                raise TimeoutError("exceeded 30s wall clock")
        except TimeoutError:
            pass
        executor.set(cost_usd=0.0104)
        raise RuntimeError("executor gave up after 2 attempts")


def normalise() -> None:
    """Replace the machine-specific fields in meta.json with example values.

    This fixture is committed, so it must not carry the absolute paths, git sha
    or pids of whoever regenerated it last. Fixing them also keeps the diff
    small when someone else regenerates on another machine.
    """
    run_dir = next(p for p in (ROOT / "runs").iterdir() if p.is_dir())
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["cwd"] = "/workspace/neuro-pipeline"
    meta["argv"] = ["python", "-m", "pipeline", "--task", "spont-eda"]
    meta["git"] = {"sha": "4f2c1ab", "branch": "feat/pca-plots", "dirty": True}
    for attempt, pid in zip(meta.get("attempts", []), (41882, 48211)):
        attempt["pid"] = pid
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")


def main() -> None:
    if len(sys.argv) > 1:
        {"one": attempt_one, "two": attempt_two}[sys.argv[1]]()
        return
    # Regenerate from scratch: aftersight resumes into an existing session
    # folder, so a leftover fixture would gain a third and fourth attempt.
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for phase in ("one", "two"):
        subprocess.run([sys.executable, __file__, phase])
    normalise()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
