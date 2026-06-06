"""Golden characterization net for the assistant SSE chat endpoint.

Pins the exact SSE event-frame sequence emitted by ``/api/assistant/chat`` for
representative scenarios. This is the safety net for the CQ7 split of
``assistant_chat`` / ``generate`` to <300 LOC (campaign doc
``2026-06-04-code-quality-7-function-split-campaign.md``): the refactor lifts
``generate()`` to a module-level ``_run_assistant_stream`` generator and
extracts the per-round tool-execution loop into ``_execute_tool_round``. Both
must preserve these frame sequences exactly — frame ORDER and PAYLOAD are
pinned, scenario-by-scenario.

Scenarios cover every code path touched by the split:
  S1 text-only response (stream loop + finalize cost/done)
  S2 one tool-use round then a text response (the extracted tool loop + multi-round)
  S3 mid-stream adapter error (the except handler)
  S4 voice mode (voice setup survives the lift; in-loop TTS wiring)
  S5 false-claim correction (the no-tool claim-check branch)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

import backend.routes.assistant_routes as ar
from backend.routes.assistant_routes import assistant_bp
from backend.services.llm_adapter import (
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
    FinishEvent,
    breakers,
)
from backend.services.llm_adapter.types import ToolCall, Usage


# ── helpers ────────────────────────────────────────────────────────────────

def _scripted_adapter(rounds):
    """A class usable as ``AnthropicAdapter(api_key=...)`` whose ``stream_chat``
    yields one scripted list of StreamEvents per tool-loop round."""
    state = {"i": 0}

    class _Fake:
        def __init__(self, *a, **k):
            pass

        def stream_chat(self, request):
            evs = rounds[state["i"]] if state["i"] < len(rounds) else []
            state["i"] += 1
            for e in evs:
                yield e

    return _Fake


def _raising_adapter(exc):
    class _Boom:
        def __init__(self, *a, **k):
            pass

        def stream_chat(self, request):
            raise exc
            yield  # pragma: no cover - makes this a generator

    return _Boom


def _parse_sse(text):
    """Parse an SSE body into the ordered list of decoded ``data:`` JSON events."""
    events = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def _clear_module_state():
    breakers._BREAKERS.clear()
    ar.conversations.clear()
    for name in (
        "cancelled_sessions",
        "tts_muted_sessions",
        "_finalizing_sessions",
        "_cost_recorded_sessions",
    ):
        s = getattr(ar, name, None)
        if s is not None:
            s.clear()


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_state():
    _clear_module_state()
    yield
    _clear_module_state()


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config["TESTING"] = True
    application.secret_key = "test-secret"

    @application.before_request
    def _set_user():
        g.user_id = "test-teacher"

    application.register_blueprint(assistant_bp)
    return application


def _drive(app, *, rounds=None, adapter=None, voice_mode=False, session_id="golden",
           extra_patches=None):
    """POST to the chat endpoint with a scripted/raising adapter and return the
    parsed SSE event list plus the raw body and any captured mocks."""
    if adapter is None:
        adapter = _scripted_adapter(rounds or [[]])

    captured = {}

    patches = [
        patch.object(ar, "_get_assistant_model",
                     return_value={"provider": "anthropic", "model": "test-model"}),
        patch("backend.api_keys.get_api_key", return_value="sk-test"),
        patch.object(ar, "anthropic", MagicMock()),
        patch.object(ar, "AnthropicAdapter", adapter),
        patch.object(ar, "_build_system_prompt", return_value="SYS"),
        patch.object(ar, "_merge_submodules", lambda: None),
        patch.object(ar, "_audit_log", lambda *a, **k: None),
        patch.object(ar, "_persist_conversation", lambda *a, **k: None),
        patch.object(ar, "_record_assistant_cost", return_value={"total_cost": 0.001}),
    ]
    if extra_patches:
        patches.extend(extra_patches)

    with _nested(patches):
        client = app.test_client()
        body = {"messages": [{"role": "user", "content": "hi"}], "session_id": session_id}
        if voice_mode:
            body["voice_mode"] = True
        resp = client.post("/api/assistant/chat", json=body)
        raw = resp.get_data(as_text=True)

    captured["status"] = resp.status_code
    captured["events"] = _parse_sse(raw)
    captured["raw"] = raw
    return captured


class _nested:
    """Enter a list of context managers, exit in reverse (3.9-friendly)."""

    def __init__(self, cms):
        self._cms = cms

    def __enter__(self):
        for cm in self._cms:
            cm.__enter__()
        return self

    def __exit__(self, *exc):
        for cm in reversed(self._cms):
            cm.__exit__(*exc)
        return False


# ── S1: text-only ──────────────────────────────────────────────────────────

def test_golden_text_only(app):
    rounds = [[
        TextDelta("Hello"),
        TextDelta(" world"),
        UsageEvent(Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.0)),
        FinishEvent("stop"),
    ]]
    with patch("backend.services.assistant_tool_guards.check_false_claims",
               return_value=None):
        out = _drive(app, rounds=rounds, session_id="s1")

    assert out["status"] == 200
    assert out["events"] == [
        {"type": "text_delta", "content": "Hello"},
        {"type": "text_delta", "content": " world"},
        {"type": "cost", "input_tokens": 10, "output_tokens": 5,
         "tts_chars": 0, "total_cost": 0.001},
        {"type": "done"},
    ]


# ── S2: one tool round then a text response ────────────────────────────────

def test_golden_tool_round(app):
    rounds = [
        [
            ToolCallDelta(tool_call_id="tc1", name="get_info", args_delta='{"q": "x"}'),
            ToolCallComplete(ToolCall(tool_call_id="tc1", name="get_info", args={"q": "x"})),
            UsageEvent(Usage(prompt_tokens=8, completion_tokens=4, cost_usd=0.0)),
            FinishEvent("tool_use"),
        ],
        [
            TextDelta("Done."),
            UsageEvent(Usage(prompt_tokens=3, completion_tokens=2, cost_usd=0.0)),
            FinishEvent("stop"),
        ],
    ]
    extra = [
        patch.object(ar, "execute_tool", return_value={"ok": True}),
        patch("backend.services.assistant_tool_guards.check_false_claims",
              return_value=None),
        patch("backend.services.assistant_tool_guards.get_verification_message",
              return_value=""),
    ]
    out = _drive(app, rounds=rounds, session_id="s2", extra_patches=extra)

    assert out["status"] == 200
    assert out["events"] == [
        {"type": "tool_start", "tool": "get_info", "id": "tc1"},
        {"type": "tool_result", "tool": "get_info", "id": "tc1",
         "result_preview": '{"ok": true}'},
        {"type": "text_delta", "content": "Done."},
        {"type": "cost", "input_tokens": 11, "output_tokens": 6,
         "tts_chars": 0, "total_cost": 0.001},
        {"type": "done"},
    ]


# ── S3: mid-stream adapter error ───────────────────────────────────────────

def test_golden_stream_error(app):
    out = _drive(app, adapter=_raising_adapter(RuntimeError("kaboom")), session_id="s3")

    assert out["status"] == 200
    assert out["events"] == [
        {"type": "error", "content": "The assistant hit an error. Please try again."},
        {"type": "done"},
    ]


# ── S4: voice mode — setup survives, TTS wiring intact ─────────────────────

def test_golden_voice_mode_wiring(app):
    rounds = [[
        TextDelta("Spoken."),
        UsageEvent(Usage(prompt_tokens=4, completion_tokens=2, cost_usd=0.0)),
        FinishEvent("stop"),
    ]]

    tts_instance = MagicMock()
    tts_instance.iter_audio.return_value = iter([])  # no audio frames -> no flaky timing

    class _FakeSentenceBuffer:
        def add(self, text):
            return [text.strip()] if text.strip() else []

        def flush(self):
            return ""

    fake_tts_module = MagicMock()
    fake_tts_module.OpenAITTSStream.return_value = tts_instance
    fake_tts_module.SentenceBuffer.return_value = _FakeSentenceBuffer()

    with patch("backend.services.assistant_tool_guards.check_false_claims",
               return_value=None), \
            patch.dict("sys.modules",
                       {"backend.services.openai_tts_service": fake_tts_module}):
        out = _drive(app, rounds=rounds, voice_mode=True, session_id="s4")

    assert out["status"] == 200
    types = [e["type"] for e in out["events"]]
    # Text streamed, stream finalized.
    assert "text_delta" in types
    assert types[-1] == "done"
    # The voice branch wired up and the in-loop TTS send survived the lift.
    tts_instance.connect.assert_called_once()
    assert tts_instance.send_text.called


# ── S5: false-claim correction (no-tool branch) ────────────────────────────

def test_golden_false_claim_correction(app):
    rounds = [[
        TextDelta("I emailed the parents."),
        UsageEvent(Usage(prompt_tokens=5, completion_tokens=5, cost_usd=0.0)),
        FinishEvent("stop"),
    ]]
    correction = " [Note: no email was actually sent.]"
    with patch("backend.services.assistant_tool_guards.check_false_claims",
               return_value=correction):
        out = _drive(app, rounds=rounds, session_id="s5")

    assert out["status"] == 200
    assert out["events"] == [
        {"type": "text_delta", "content": "I emailed the parents."},
        {"type": "text", "content": correction},
        {"type": "cost", "input_tokens": 5, "output_tokens": 5,
         "tts_chars": 0, "total_cost": 0.001},
        {"type": "done"},
    ]
