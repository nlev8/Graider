"""LLM provider adapter layer (Phase 5a PR D1 + D2)."""
from backend.services.llm_adapter.types import (
    ContentPart,
    DEFAULT_TIMEOUT,
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    ResponseFormat,
    TextPart,
    ToolCall,
    ToolDef,
    ToolResultPart,
    ToolUsePart,
    Usage,
)

from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)

from backend.services.llm_adapter.anthropic_adapter import AnthropicAdapter
from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
from backend.services.llm_adapter.openai_adapter import OpenAIAdapter

__all__ = [
    # Adapters
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    # Request / response types (D1)
    "ContentPart",
    "DEFAULT_TIMEOUT",
    "ImagePart",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "ResponseFormat",
    "TextPart",
    "ToolCall",
    "ToolDef",
    "ToolResultPart",
    "ToolUsePart",
    "Usage",
    # Stream event types (D2)
    "FinishEvent",
    "StreamEvent",
    "TextDelta",
    "ToolCallComplete",
    "ToolCallDelta",
    "UsageEvent",
]
