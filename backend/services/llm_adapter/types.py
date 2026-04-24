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
    # OpenAI-only vision-detail hint. Valid values: "auto" (default),
    # "low" (512x512 thumbnail, ~85 tokens), "high" (original resolution,
    # up to ~170 tokens per 512-px tile). Other providers silently ignore.
    detail: Literal["auto", "low", "high"] | None = None


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


# ---- Finish reason normalization --------------------------------------

# Canonical finish_reason values returned by LLMResponse — downstream code
# should switch on exactly these 4 strings. Provider SDKs emit different
# native names; each adapter calls normalize_finish_reason() to map to
# these canonicals. Unmapped values are passed through (lowercased) so
# operators still see what the provider actually said, but downstream
# logic should treat anything unexpected as "stop" (the safe default).
_FINISH_REASON_MAP = {
    # OpenAI native → canonical
    "stop": "stop",
    "length": "length",
    "tool_calls": "tool_use",
    "tool_use": "tool_use",
    "function_call": "tool_use",
    "content_filter": "content_filter",
    # Anthropic native → canonical
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "stop",
    # Gemini native → canonical (finish_reason enum as uppercased string)
    "max_tokens_reached": "length",
    "safety": "content_filter",
    "recitation": "content_filter",
    "blocklist": "content_filter",
    "prohibited_content": "content_filter",
    "spii": "content_filter",
    "other": "stop",
    "malformed_function_call": "tool_use",
    "finish_reason_unspecified": "stop",
    "unexpected_tool_call": "tool_use",
    "image_safety": "content_filter",
}


def normalize_finish_reason(raw: str | None) -> str:
    """Map a provider-native finish_reason to one of the 4 canonical values."""
    if not raw:
        return "stop"
    return _FINISH_REASON_MAP.get(str(raw).lower(), str(raw).lower())


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


class LLMToolArgsOverflow(Exception):
    """Tool-call args exceeded the adapter's streaming buffer cap.

    Raised from streaming adapters (OpenAI, Anthropic) when accumulated
    tool_call.arguments payload would exceed MAX_TOOL_ARGS_BYTES. Gemini
    is exempt — it delivers args atomically, no incremental growth path.

    Phase 5b PR 5 — see docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md
    """
