"""aftersight + the Claude Agent SDK, in one file.

    npm install -g @anthropic-ai/claude-code
    pip install aftersight claude-agent-sdk
    export ANTHROPIC_API_KEY=sk-ant-...
    python claude_agent_sdk_starter.py

The SDK emits no in-process OpenTelemetry spans today, so this wraps the query
in an explicit span and copies the cost and turn count the SDK reports back
into it. If a future version emits `gen_ai.*` spans, they are picked up
automatically and the wrapper becomes redundant.
"""

import asyncio

import aftersight
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query


async def ask(prompt: str) -> str:
    with aftersight.span("claude", kind="agent") as s:
        parts: list[str] = []
        async for message in query(prompt=prompt):
            if isinstance(message, AssistantMessage):
                parts += [b.text for b in message.content if isinstance(b, TextBlock)]
            elif isinstance(message, ResultMessage):
                s.set(cost_usd=message.total_cost_usd, turns=message.num_turns)
        s.output = "".join(parts)
        return s.output


def main() -> None:
    with aftersight.start(framework="claude-agent-sdk") as run:
        print(asyncio.run(ask("In one sentence, what is in this directory?")))

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
