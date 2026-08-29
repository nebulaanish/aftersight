# CLI

Two commands. Everything else you would want is `rg` and `jq` on the run folder,
which is the point of the format.

## aftersight run

```bash
aftersight run [--session SESSION] [--root ROOT] <command> [args...]
```

Runs a command with recording enabled and no change to its source. The exit code
is passed through, so it is safe in a `Makefile` or CI step.

```bash
aftersight run python my_agent.py
aftersight run --session nightly python -m my_pipeline --task eda
aftersight run pytest tests/test_agent.py
```

`--session` sets the session id, so repeated invocations append into one run
folder. `--root` overrides the telemetry root for this invocation.

### How it attaches

A generated `sitecustomize.py` is placed on `PYTHONPATH` for the child process,
which is the mechanism coverage tools use to instrument an interpreter they do
not control. It works through `uv run`, `pytest` and any wrapper that eventually
execs Python, and it chains to your project's own `sitecustomize` if you have
one.

If the program you are running is not Python, nothing is recorded and the
command still runs normally.

## aftersight skill

```bash
aftersight skill [--into .claude/skills]
```

Installs the Claude Code skill that tells a coding agent this telemetry exists,
how the `#seq` anchors work, and which counting mistakes produce wrong answers.

```bash
aftersight skill
# installed .claude/skills/aftersight/SKILL.md
```

`--into` points at a different skills directory if your setup uses one.
