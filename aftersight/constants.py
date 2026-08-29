from __future__ import annotations

# Dotted on purpose: `rg 'tool\.'` finds all tool activity, `rg '\.error'`
# finds every failure shape.


class EventType:
    RUN_START = "run.start"
    RUN_RESUME = "run.resume"
    RUN_END = "run.end"
    AGENT_START = "agent.start"
    AGENT_END = "agent.end"
    LLM_PROMPT = "llm.prompt"
    LLM_RESPONSE = "llm.response"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TOOL_ERROR = "tool.error"
    ERROR = "error"
    LOG = "log"


# Pointers live outside RUNS_DIR so a `runs/*/...` glob cannot count a run twice.

DEFAULT_ROOT = ".runs"
RUNS_DIR = "runs"
SESSIONS_DIR = "sessions"
LATEST_LINK = "latest"
NAVIGATE_FILE = "NAVIGATE.md"
INDEX_FILE = "index.jsonl"
GITIGNORE_MARK = "# aftersight"

TRANSCRIPT_FILE = "agent.logs"
TRACE_FILE = "trace.jsonl"
OUTLINE_FILE = "outline.md"
ANALYTICS_FILE = "analytics.json"
META_FILE = "meta.json"
BLOBS_DIR = "blobs"
ARTIFACTS_DIR = "artifacts"

RUN_ID_TIME_FORMAT = "%Y%m%d_%H%M%S"
RUN_ID_SUFFIX_LEN = 4

DEFAULT_KEEP_RUNS = 50
DEFAULT_BLOB_MAX_BYTES = 8192
DEFAULT_BLOB_PREVIEW_LINES = 12

ENV_ENABLED = "AFTERSIGHT"
ENV_ROOT = "AFTERSIGHT_ROOT"
ENV_KEEP_RUNS = "AFTERSIGHT_KEEP_RUNS"
ENV_BLOB_MAX = "AFTERSIGHT_BLOB_MAX"
ENV_OTEL = "AFTERSIGHT_OTEL"
ENV_LOGGING = "AFTERSIGHT_LOGGING"
ENV_REDACT = "AFTERSIGHT_REDACT"
ENV_QUIET = "AFTERSIGHT_QUIET"
ENV_AUTOSTART = "AFTERSIGHT_AUTOSTART"
ENV_SESSION = "AFTERSIGHT_SESSION"

TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}

FRAME_WIDTH = 70
INLINE_ARG_LIMIT = 200
INLINE_BLOCK_LIMIT = 120
OUTLINE_NAME_COL = 28

#: Payload keys the transcript renders itself, so the generic key=value tail
#: does not repeat them.
RENDERED_PAYLOAD_KEYS = {"text", "text_ref", "preview", "bytes"}

TRANSCRIPT_TIME_FORMAT = "%H:%M:%S"
BANNER_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

REDACTION_MASK = "[REDACTED]"

#: A pattern with a capture group masks only the group, so the surrounding
#: `api_key=` stays readable.
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{16,}",
    r"(?i:bearer)\s+[A-Za-z0-9._\-]{16,}",
    r"(?i:(?:api[_-]?key|secret|token|password)\"?\s*[:=]\s*\"?)([A-Za-z0-9._\-]{12,})",
    r"gh[pousr]_[A-Za-z0-9]{16,}",
    r"AKIA[0-9A-Z]{16}",
]

# Three are read: OTel `gen_ai.*` semantic conventions, OpenInference `llm.*`,
# and a generic `input.value` / `output.value` fallback. Add an attribute name
# here rather than at a call site.

SPAN_KIND_ATTRS = ("openinference.span.kind", "gen_ai.operation.name",
                   "traceloop.span.kind")

LLM_SPAN_KINDS = {"LLM", "chat", "text_completion", "generate_content"}
TOOL_SPAN_KINDS = {"TOOL", "execute_tool"}
CONTAINER_SPAN_KINDS = {"AGENT", "CHAIN", "GRAPH", "WORKFLOW", "invoke_agent",
                        "create_agent"}

#: Indexed message attributes, joined into one text block.
PROMPT_TEMPLATES = ("gen_ai.prompt.{i}.content", "llm.input_messages.{i}.message.content")
COMPLETION_TEMPLATES = ("gen_ai.completion.{i}.content",
                        "llm.output_messages.{i}.message.content")

PROMPT_ATTRS = ("gen_ai.prompt", "input.value", "llm.prompts")
COMPLETION_ATTRS = ("gen_ai.completion", "output.value")
MODEL_ATTRS = ("gen_ai.request.model", "llm.model_name")
TOOL_NAME_ATTRS = ("tool.name", "gen_ai.tool.name")
TOOL_ARG_ATTRS = ("tool.parameters", "input.value")
COST_ATTRS = ("gen_ai.usage.cost", "llm.cost.total")
FINISH_REASON_ATTRS = ("gen_ai.response.finish_reasons",)
INPUT_TOKEN_ATTRS = ("gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens",
                     "llm.token_count.prompt")
OUTPUT_TOKEN_ATTRS = ("gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens",
                      "llm.token_count.completion")

MAX_INDEXED_MESSAGES = 64

#: OpenInference instrumentors activated when already installed. Nothing is
#: installed on the user's behalf.
INSTRUMENTORS = [
    ("openinference.instrumentation.agno", "AgnoInstrumentor", "agno"),
    ("openinference.instrumentation.langchain", "LangChainInstrumentor", "langchain"),
    ("openinference.instrumentation.crewai", "CrewAIInstrumentor", "crewai"),
    ("openinference.instrumentation.llama_index", "LlamaIndexInstrumentor", "llama-index"),
    ("openinference.instrumentation.openai_agents", "OpenAIAgentsInstrumentor", "openai-agents"),
    ("openinference.instrumentation.smolagents", "SmolagentsInstrumentor", "smolagents"),
]
