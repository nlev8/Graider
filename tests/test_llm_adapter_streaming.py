"""Tests for the streaming stream-event types (Phase 5a PR D2)."""
from __future__ import annotations

import pytest

from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import ToolCall, Usage


def test_text_delta():
    e = TextDelta(text="hello")
    assert isinstance(e, (TextDelta,))
    assert e.text == "hello"


def test_tool_call_delta_incremental():
    e = ToolCallDelta(tool_call_id="abc", name="weather", args_delta='{"loc')
    assert e.tool_call_id == "abc"
    assert e.name == "weather"
    assert e.args_delta == '{"loc'


def test_tool_call_delta_continuation_has_no_name():
    """Subsequent deltas for the same call have name=None."""
    e = ToolCallDelta(tool_call_id="abc", name=None, args_delta='ation": "SF"}')
    assert e.name is None


def test_tool_call_complete():
    tc = ToolCall(tool_call_id="abc", name="weather", args={"loc": "SF"})
    e = ToolCallComplete(tool_call=tc)
    assert e.tool_call.name == "weather"
    assert e.tool_call.args == {"loc": "SF"}


def test_usage_event_wraps_usage():
    e = UsageEvent(usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001))
    assert e.usage.prompt_tokens == 10
    assert e.usage.completion_tokens == 5
    assert e.usage.cost_usd == 0.001


def test_finish_event():
    e = FinishEvent(finish_reason="tool_use")
    assert e.finish_reason == "tool_use"


def test_finish_event_stop():
    e = FinishEvent(finish_reason="stop")
    assert e.finish_reason == "stop"


def test_stream_events_are_frozen():
    """All event types must be immutable (frozen=True)."""
    e = TextDelta(text="hi")
    with pytest.raises(Exception):
        e.text = "mutated"  # type: ignore[misc]


def test_stream_event_type_alias_covers_all_types():
    """StreamEvent is a Union — verify each concrete type is recognised."""
    events = [
        TextDelta(text="a"),
        ToolCallDelta(tool_call_id="x", name="fn", args_delta="{}"),
        ToolCallComplete(tool_call=ToolCall(tool_call_id="x", name="fn", args={})),
        UsageEvent(usage=Usage(prompt_tokens=1, completion_tokens=1, cost_usd=0.0)),
        FinishEvent(finish_reason="stop"),
    ]
    for ev in events:
        # Each is an instance of its concrete class
        assert isinstance(ev, (TextDelta, ToolCallDelta, ToolCallComplete, UsageEvent, FinishEvent))
