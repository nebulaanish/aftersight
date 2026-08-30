# aftersight

Observability infrastructure for self-improving agents.

An agent cannot improve on a run it cannot read. Aftersight writes every
run into the repository as plain files, so the agent can read its own
history with the tools it already has.

Those files are readable by a person and machine-readable by a client. An agent
uses its normal file and shell tools to diagnose one failed run, find recurring
failures and inspect exact model or tool inputs and outputs.

```bash
pip install aftersight
aftersight run python my_agent.py
```

Then ask:

> Read `.runs/NAVIGATE.md` and find out why the latest run failed.

There is no account, API key, service or initialization step. Aftersight itself
makes no network requests, and payload redaction is enabled by default.

## Where to go next

- [Why aftersight exists](why.md) explains the local, agent-native design.
- [Quickstart](quickstart.md) records a first run.
- [Frameworks](frameworks.md) covers OpenTelemetry and framework setup.
- [Navigating runs](navigating.md) contains the search workflow.
- [Run folder format](reference/run-folder.md) documents every generated file.

!!! note "Local durability"
    Aftersight can run in production, but local filesystem data may disappear
    with an ephemeral, replaced or failed host. Use durable storage or another
    telemetry export path when the run history must survive the host.
