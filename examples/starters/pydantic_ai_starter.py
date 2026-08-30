"""aftersight + pydantic-ai, in one file.

    pip install aftersight pydantic-ai
    export OPENAI_API_KEY=sk-...
    python pydantic_ai_starter.py

pydantic-ai emits OpenTelemetry natively, so `instrument_all()` is the only
extra line. Every model call, tool call and token count lands in the run
folder printed at the end.
"""

import aftersight
from pydantic_ai import Agent


def main() -> None:
    with aftersight.start(framework="pydantic-ai", model="gpt-4o-mini") as run:
        Agent.instrument_all()

        agent = Agent("openai:gpt-4o-mini",
                      system_prompt="Answer in one short sentence.")
        result = agent.run_sync("Why is a failed agent run hard to debug?")
        print(result.output)

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
