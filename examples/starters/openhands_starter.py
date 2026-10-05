"""aftersight + the OpenHands SDK, in one file.

    pip install aftersight openhands-sdk openhands-tools
    export LLM_API_KEY=sk-...
    python openhands_starter.py

OpenHands emits no OpenTelemetry itself, but its model calls go through
LiteLLM, and LiteLLM's "otel" callback reports each one to the tracer
`aftersight.start()` set up. The OpenInference LiteLLM instrumentor cannot do
this: OpenHands holds its own reference to `litellm.completion`, which the
instrumentor never patches. Everything else arrives through the logging
bridge, and `log_level=logging.INFO` keeps the whole story instead of only
the warnings and errors captured by default, at the cost of a larger trace.
"""

import logging
import os

import aftersight
import litellm
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from pydantic import SecretStr


def main() -> None:
    with aftersight.start(framework="openhands", model="gpt-4o-mini",
                          log_level=logging.INFO) as run:
        litellm.callbacks = ["otel"]
        llm = LLM(model="gpt-4o-mini", usage_id="starter",
                  api_key=SecretStr(os.environ["LLM_API_KEY"]))
        agent = Agent(llm=llm, tools=[Tool(name=FileEditorTool.name)])

        with aftersight.span("openhands", kind="agent"):
            # Absolute, because the file editor rejects relative paths and the
            # agent is told this path as its working directory.
            conversation = Conversation(agent=agent,
                                        workspace=os.path.abspath("workspace"))
            conversation.send_message("Write hello.txt containing the word hello.")
            conversation.run()

    print(f"\nread the run: {run.dir}/outline.md")


if __name__ == "__main__":
    main()
