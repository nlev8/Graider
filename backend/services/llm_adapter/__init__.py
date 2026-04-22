"""LLM provider adapter layer (Phase 5a PR D1 + D2)."""
from typing import Iterator, Protocol, runtime_checkable

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


@runtime_checkable
class LLMAdapter(Protocol):
    """Structural-typing contract all LLM adapters implement.

    Consumers that want to accept "any LLM adapter" without importing a
    specific provider class should type-annotate against this Protocol.
    `isinstance(adapter, LLMAdapter)` works at runtime thanks to
    @runtime_checkable.

    All three shipping adapters (OpenAIAdapter, AnthropicAdapter,
    GeminiAdapter) already satisfy this by structure — the Protocol is
    added for typed clarity, not as a new required base class.
    """

    def chat(self, request: LLMRequest) -> LLMResponse: ...

    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]: ...


__all__ = [
    # Adapters + Protocol
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    "LLMAdapter",
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
