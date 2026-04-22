"""Type definitions for the LLM provider adapter layer (Phase 5a PR D1).

See docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR D1
for design rationale. The shapes below are driven by the live repo's
current call sites (multimodal input, tool use, system prompts).

All types are frozen dataclasses — immutable value objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union


# ---- ContentPart union -------------------------------------------------

@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    # Exactly one of url or base64 must be set.
    url: str | None
    base64: str | None
    mime_type: str  # e.g. "image/png", "image/jpeg"


@dataclass(frozen=True)
class ToolUsePart:
    """Assistant-side: the model wants to call a tool."""
    tool_call_id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResultPart:
    """User-side: result fed back in response to a prior ToolUsePart."""
    tool_call_id: str
    content: str | dict[str, Any]  # stringified result or structured data


# Python doesn't have a real union base class without PEP 604, so use a
# type alias. isinstance() checks work against the concrete types.
ContentPart = Union[TextPart, ImagePart, ToolUsePart, ToolResultPart]


# ---- Message wrapper ---------------------------------------------------

@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant", "tool"]
    content: list[ContentPart]
    # Set when role == "tool"; mirrors the tool_call_id of the
    # corresponding ToolResultPart for providers that need it at the
    # message level (e.g. OpenAI).
    tool_call_id: str | None = None


# ---- Tool definitions --------------------------------------------------

@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str
    name: str
    args: dict[str, Any]


# ---- Response format ---------------------------------------------------

@dataclass(frozen=True)
class ResponseFormat:
    # "text" (default) or "json_object" / "json_schema"
    type: Literal["text", "json_object", "json_schema"]
    schema: dict[str, Any] | None = None  # required if type == "json_schema"


# ---- Usage -------------------------------------------------------------

@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# ---- Request / Response ------------------------------------------------

DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[Message]
    system_prompt: str | None = None
    tools: list[ToolDef] | None = None
    response_format: ResponseFormat | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    timeout: float = DEFAULT_TIMEOUT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content_parts: list[ContentPart]
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str  # "stop" | "length" | "tool_use" | "content_filter"
    provider: str  # "openai" | "anthropic" | "gemini"
    model: str
