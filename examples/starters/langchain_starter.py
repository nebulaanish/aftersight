"""aftersight + LangChain agents, which run on LangGraph, in one file.

    pip install "aftersight[langchain]" langchain langchain-openai
    export OPENAI_API_KEY=sk-...
    python langchain_starter.py

The OpenInference instrumentor is activated by `aftersight.start()` when it is
installed, so the graph steps, model calls and tool calls all arrive as spans.
"""

import aftersight
from langchain.agents import create_agent
from langchain.tools import tool


@tool
def word_count(text: str) -> int:
    """Count the words in a piece of text."""
    return len(text.split())


def main() -> None:
    with aftersight.start(framework="langchain", model="gpt-4o-mini") as run:
        agent = create_agent(
            "openai:gpt-4o-mini",
            tools=[word_count],
            system_prompt="Use your tools instead of guessing.",
        )
        question = "How many words are in 'the quick brown fox'?"
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        print(result["messages"][-1].content)

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
