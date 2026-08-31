"""aftersight + the OpenAI Agents SDK, in one file.

    pip install "aftersight[openai-agents]" openai-agents
    export OPENAI_API_KEY=sk-...
    python openai_agents_starter.py

`aftersight.start()` switches on any OpenInference instrumentor it finds
installed, so the agent loop and its tool calls are captured without a line
of framework-specific code. The `[openai-agents]` extra above is what puts
that instrumentor there; without it the run records no llm or tool calls and
`start()` says so on stderr. Nothing is installed at runtime on your behalf.
"""

import aftersight
from agents import Agent, Runner, function_tool


@function_tool
def word_count(text: str) -> int:
    """Count the words in a piece of text."""
    return len(text.split())


def main() -> None:
    with aftersight.start(framework="openai-agents", model="gpt-4o-mini") as run:
        agent = Agent(
            name="counter",
            model="gpt-4o-mini",
            instructions="Use your tools instead of guessing.",
            tools=[word_count],
        )
        result = Runner.run_sync(agent, "How many words are in 'the quick brown fox'?")
        print(result.final_output)

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
