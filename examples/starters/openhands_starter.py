"""aftersight + the OpenHands SDK, in one file.

    pip install aftersight openhands-sdk openhands-tools
    export LLM_API_KEY=sk-...
    python openhands_starter.py

OpenHands reports its progress through stdlib logging rather than
OpenTelemetry, so aftersight's logging bridge carries the narrative.
`log_level=logging.INFO` keeps the whole story instead of only the warnings
and errors captured by default, at the cost of a much larger trace.
"""

import logging
import os

import aftersight
from openhands.sdk import LLM, Agent, Conversation
from pydantic import SecretStr


def main() -> None:
    with aftersight.start(framework="openhands", model="gpt-4o-mini",
                          log_level=logging.INFO) as run:
        llm = LLM(model="gpt-4o-mini", usage_id="starter",
                  api_key=SecretStr(os.environ["LLM_API_KEY"]))
        agent = Agent(llm=llm, tools=[])

        with aftersight.span("openhands", kind="agent"):
            conversation = Conversation(agent=agent, workspace="./workspace")
            conversation.send_message("Write hello.txt containing the word hello.")
            conversation.run()

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
