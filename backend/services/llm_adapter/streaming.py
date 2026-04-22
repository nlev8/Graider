"""Streaming stream-event types for Phase 5a PR D2.

See docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR D2
for design rationale.

StreamEvent is a discriminated union of five frozen dataclasses. Adapters
yield these from stream_chat(); consumers branch on isinstance() checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from backend.services.llm_adapter.types import ToolCall, Usage


@dataclass(frozen=True)
class TextDelta:
    """Incremental text chunk from the model's streaming response."""
    text: str


@dataclass(frozen=True)
class ToolCallDelta:
    """Partial tool-call state during streaming.

    Provider-native tool-call streaming emits arg-delta chunks; adapters
    normalize those into this event. Consumers assemble the complete
    tool call by concatenating `args_delta` across all deltas sharing
    the same `tool_call_id`, OR wait for the ToolCallComplete event.

    `name` is present only on the first delta for a given tool_call_id;
    subsequent deltas carry name=None.
    """
    tool_call_id: str
    name: str | None  # present on the first delta for a given call
    args_delta: str  # JSON fragment


@dataclass(frozen=True)
class ToolCallComplete:
    """Emitted after all deltas for a tool call have assembled."""
    tool_call: ToolCall


@dataclass(frozen=True)
class UsageEvent:
    """Final usage report, emitted at end of stream."""
    usage: Usage


@dataclass(frozen=True)
class FinishEvent:
    """End of stream marker."""
    finish_reason: str  # "stop" | "length" | "tool_use" | "content_filter"


# Discriminated union — isinstance() against the concrete types works.
StreamEvent = Union[TextDelta, ToolCallDelta, ToolCallComplete, UsageEvent, FinishEvent]
