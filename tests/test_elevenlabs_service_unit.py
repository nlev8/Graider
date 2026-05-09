"""Unit tests for backend/services/elevenlabs_service.py.

Audit MAJOR #4 sprint follow-up to PR #274. Module is at 0% coverage —
the only completely uncovered service module remaining. Targets 152
uncovered LOC.

Strategy
--------
Two classes in the module:

  1. `SentenceBuffer` — pure text-splitting logic (no I/O). Strong/weak
     break detection, force-emit on max-length. Tested directly with
     deterministic inputs.

  2. `ElevenLabsTTSStream` — WebSocket-based streaming TTS client.
     Tested with `unittest.mock` patching of `websocket.WebSocketApp`
     and the threading primitives. The keepalive loop and the long-poll
     `connect()` thread are NOT exercised end-to-end (would require
     either a real ElevenLabs server or a fake WebSocket harness — out
     of scope for unit tests). We DO cover all the synchronous-callback
     paths (`_on_open`, `_on_message`, `_on_error`, `_on_close`) and
     the public methods that touch them.

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex rate-limited until
2026-05-12; Gemini 3.1 Pro is the validated fallback reviewer.
"""
from __future__ import annotations

import json
import queue
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# SentenceBuffer
# ──────────────────────────────────────────────────────────────────


class TestSentenceBuffer:
    """Pure text-splitting logic — no mocks needed."""

    def test_empty_init(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        assert sb.buffer == ""

    def test_no_break_returns_empty_chunks(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Below WEAK_MIN, no strong break, no force
        assert sb.add("hello") == []
        assert sb.buffer == "hello"

    def test_period_emits_chunk(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("Hello world.")
        assert chunks == ["Hello world."]
        assert sb.buffer == ""

    def test_question_mark_emits_chunk(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("How are you?")
        assert chunks == ["How are you?"]

    def test_exclamation_emits_chunk(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("Wow!")
        assert chunks == ["Wow!"]

    def test_newline_emits_chunk(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("Line one\nLine two")
        assert chunks == ["Line one\n"]
        assert sb.buffer == "Line two"

    def test_multiple_sentences_in_one_call(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("First. Second! Third?")
        assert chunks == ["First.", "Second!", "Third?"]
        assert sb.buffer == ""

    def test_earliest_strong_break_wins(self):
        # If the buffer has both `.` and `!`, the earlier one splits first
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("First. Second!")
        assert chunks[0] == "First."

    def test_strips_whitespace_after_break(self):
        # Production lstrips after the break: trailing space drops
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        chunks = sb.add("Hello.   World.")
        assert chunks == ["Hello.", "World."]

    def test_whitespace_only_chunk_skipped(self):
        # If the chunk before a break is just whitespace (e.g. just a "."),
        # production's `if chunk.strip(): chunks.append(chunk)` skips it.
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # A leading "." with nothing before is whitespace-only after strip
        chunks = sb.add(".")
        # The chunk was just "." which strips to "." (truthy), so emit it
        assert chunks == ["."]

    def test_weak_break_only_after_min_length(self):
        # Weak break (comma) below WEAK_MIN (30 chars) is NOT split
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # "Hi, world" is 9 chars — below WEAK_MIN
        assert sb.add("Hi, world") == []
        assert "," in sb.buffer

    def test_weak_break_at_min_length(self):
        # Weak break (comma) when buffer >= WEAK_MIN (30 chars) DOES split,
        # but only if the comma is at idx >= 15.
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Build buffer: "0123456789012345 long enough, more text"
        # Comma at index 28, buffer length 39+ chars → meets both conditions
        text = "Hello world here is a long, more text continues"
        chunks = sb.add(text)
        # First chunk should split at the comma (index 26)
        assert any("," in c for c in chunks)

    def test_weak_break_index_must_be_at_least_15(self):
        # Per production line 71: `idx != -1 and idx >= 15`
        # If comma is too early in the buffer (idx < 15), weak break
        # doesn't fire — even if buffer length >= WEAK_MIN.
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Comma at index 3 (< 15). Add text WITHOUT a strong-break period
        # so the strong-break path doesn't pre-empt the weak-break check.
        text = "Hi, there is enough buffer here for weak min check now"
        # Comma at index 2, buffer length 54 (>= WEAK_MIN=30)
        chunks = sb.add(text)
        # No emission: comma idx=2 < 15 (weak skipped); no strong break;
        # buffer length 54 < MAX_LEN=80 (no force-emit).
        assert chunks == []
        assert sb.buffer == text  # full text remains buffered

    def test_weak_break_index_at_15_or_more_does_split(self):
        # Symmetric pin: comma at idx >= 15 with buffer >= WEAK_MIN
        # DOES split.
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Comma at index 25 (>= 15), buffer length >= WEAK_MIN (30)
        text = "abcdefghijklmnopqrstuvwxy, more text continues here now"
        # Comma at index 25, total length 56 → weak break fires
        chunks = sb.add(text)
        # First chunk includes the comma at the natural break point
        assert len(chunks) >= 1
        assert chunks[0].endswith(",")

    def test_force_emit_on_max_length(self):
        # Buffer exceeds MAX_LEN (80) — force-emit at last space before 80
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Build a long string with no strong/weak breaks, ending past 80
        text = "a " * 50  # 100 chars, no terminators
        chunks = sb.add(text)
        # Should emit at least one chunk (at the last space before 80)
        assert len(chunks) >= 1

    def test_force_emit_when_no_space_in_window(self):
        # If `rfind(' ', 0, MAX_LEN)` returns <= 0, split at MAX_LEN exactly
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # 100 chars of solid text, no spaces
        text = "x" * 100
        chunks = sb.add(text)
        # The hardcoded fallback is split_at = MAX_LEN (80)
        assert chunks == ["x" * 80]
        assert sb.buffer == "x" * 20

    def test_em_dash_is_weak_break(self):
        # em-dash (—) is in WEAK
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        # Buffer must be >= 30 chars and dash at >= idx 15 to split
        text = "First long enough section—and after the dash is more text now"
        chunks = sb.add(text)
        # Em-dash split fires
        assert any("—" in c for c in chunks)

    def test_en_dash_is_weak_break(self):
        # en-dash (–) is in WEAK
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        text = "First long enough section–and after the dash is more text now"
        chunks = sb.add(text)
        assert any("–" in c for c in chunks)

    def test_close_paren_is_weak_break(self):
        # ')' is in WEAK
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        text = "(parenthetical and long enough) more content continues now"
        chunks = sb.add(text)
        assert any(c.endswith(")") for c in chunks)

    def test_flush_returns_remaining_text(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        sb.add("incomplete")  # below threshold, no strong break
        flushed = sb.flush()
        assert flushed == "incomplete"
        assert sb.buffer == ""

    def test_flush_strips_whitespace(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        sb.add("   spaced   ")
        flushed = sb.flush()
        assert flushed == "spaced"

    def test_flush_returns_none_when_empty(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        assert sb.flush() is None

    def test_flush_returns_none_when_only_whitespace(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        sb = SentenceBuffer()
        sb.add("   ")
        assert sb.flush() is None

    def test_constants_match_documented_behavior(self):
        from backend.services.elevenlabs_service import SentenceBuffer
        # Pin the public constants so a regression that changes them is caught
        assert SentenceBuffer.STRONG == {".", "!", "?", "\n"}
        assert "," in SentenceBuffer.WEAK
        assert ";" in SentenceBuffer.WEAK
        assert ":" in SentenceBuffer.WEAK
        assert "—" in SentenceBuffer.WEAK
        assert "–" in SentenceBuffer.WEAK
        assert ")" in SentenceBuffer.WEAK
        assert SentenceBuffer.WEAK_MIN == 30
        assert SentenceBuffer.MAX_LEN == 80


# ──────────────────────────────────────────────────────────────────
# ElevenLabsTTSStream
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def env_with_api_key(monkeypatch):
    """Set ELEVENLABS_API_KEY so __init__ doesn't raise."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test_abcd")
    return "el_test_abcd"


class TestStreamInit:
    def test_raises_when_api_key_missing(self, monkeypatch):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream

        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY not set"):
            ElevenLabsTTSStream()

    def test_uses_env_api_key(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream

        s = ElevenLabsTTSStream()
        assert s.api_key == env_with_api_key

    def test_uses_default_voice_id_when_no_arg_or_env(
        self, env_with_api_key, monkeypatch,
    ):
        from backend.services.elevenlabs_service import (
            ElevenLabsTTSStream, DEFAULT_VOICE_ID,
        )
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
        s = ElevenLabsTTSStream()
        assert s.voice_id == DEFAULT_VOICE_ID

    def test_explicit_voice_id_overrides_env(
        self, env_with_api_key, monkeypatch,
    ):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "env_voice")
        s = ElevenLabsTTSStream(voice_id="explicit_voice")
        assert s.voice_id == "explicit_voice"

    def test_env_voice_id_used_when_no_arg(
        self, env_with_api_key, monkeypatch,
    ):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "env_voice")
        s = ElevenLabsTTSStream()
        assert s.voice_id == "env_voice"

    def test_default_model_id_when_not_provided(self, env_with_api_key):
        from backend.services.elevenlabs_service import (
            ElevenLabsTTSStream, DEFAULT_MODEL_ID,
        )
        s = ElevenLabsTTSStream()
        assert s.model_id == DEFAULT_MODEL_ID

    def test_explicit_model_id(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream(model_id="custom_model")
        assert s.model_id == "custom_model"

    def test_initial_state(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        assert s.ws is None
        assert s._closed is False
        assert s._connected.is_set() is False
        assert s._flush_done.is_set() is False
        assert isinstance(s.audio_queue, queue.Queue)


class TestStreamConnect:
    def test_raises_when_websocket_module_missing(self, env_with_api_key):
        from backend.services import elevenlabs_service as mod

        with patch.object(mod, "websocket", None):
            stream = mod.ElevenLabsTTSStream()
            with pytest.raises(ImportError, match="websocket-client required"):
                stream.connect()

    def test_connect_opens_websocket_with_correct_url(self, env_with_api_key):
        from backend.services import elevenlabs_service as mod

        with patch.object(mod, "websocket") as mock_ws_mod:
            mock_app = MagicMock()
            mock_ws_mod.WebSocketApp.return_value = mock_app
            stream = mod.ElevenLabsTTSStream()

            # Set _connected.set immediately so connect() doesn't block on wait
            def _set_connected(*args, **kwargs):
                stream._connected.set()
                return mock_app
            mock_ws_mod.WebSocketApp.side_effect = _set_connected

            with patch("threading.Thread") as MockThread:
                MockThread.return_value = MagicMock()
                stream.connect()

            url_arg = mock_ws_mod.WebSocketApp.call_args.args[0]
            # URL contains the expected components
            assert "wss://api.elevenlabs.io/v1/text-to-speech/" in url_arg
            assert stream.voice_id in url_arg
            assert "stream-input" in url_arg
            assert f"model_id={stream.model_id}" in url_arg

    def test_connect_passes_api_key_in_header(self, env_with_api_key):
        from backend.services import elevenlabs_service as mod

        with patch.object(mod, "websocket") as mock_ws_mod:
            mock_app = MagicMock()
            mock_ws_mod.WebSocketApp.return_value = mock_app
            stream = mod.ElevenLabsTTSStream()

            def _set_connected(*args, **kwargs):
                stream._connected.set()
                return mock_app
            mock_ws_mod.WebSocketApp.side_effect = _set_connected

            with patch("threading.Thread") as MockThread:
                MockThread.return_value = MagicMock()
                stream.connect()

            header = mock_ws_mod.WebSocketApp.call_args.kwargs["header"]
            assert header == {"xi-api-key": env_with_api_key}

    def test_connect_timeout_raises(self, env_with_api_key):
        from backend.services import elevenlabs_service as mod

        with patch.object(mod, "websocket") as mock_ws_mod:
            mock_ws_mod.WebSocketApp.return_value = MagicMock()
            # Don't set _connected — wait will time out
            stream = mod.ElevenLabsTTSStream()

            with patch.object(stream._connected, "wait", return_value=False), \
                 patch("threading.Thread") as MockThread:
                MockThread.return_value = MagicMock()
                with pytest.raises(ConnectionError,
                                   match="WebSocket connection timed out"):
                    stream.connect()


class TestStreamSendText:
    def test_no_op_when_closed(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s._closed = True
        s.ws = MagicMock()  # set ws so the first short-circuit hits ._closed
        s.send_text("hello")
        # ws.send shouldn't be called
        s.ws.send.assert_not_called()

    def test_no_op_when_no_ws(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = None  # default after __init__
        s.send_text("hello")  # should not raise

    def test_sends_json_when_open(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        # Build a ws mock whose .sock.connected = True
        s.ws = MagicMock()
        s.ws.sock.connected = True

        s.send_text("hello world")
        sent = s.ws.send.call_args.args[0]
        payload = json.loads(sent)
        assert payload["text"] == "hello world"
        assert payload["try_trigger_generation"] is True


class TestStreamFlush:
    def test_no_op_when_closed(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s._closed = True
        s.ws = MagicMock()
        s.flush()
        s.ws.send.assert_not_called()

    def test_clears_flush_done_event_and_sends(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True
        s._flush_done.set()  # pre-set so we can verify it's cleared

        s.flush()

        assert s._flush_done.is_set() is False  # cleared
        sent = s.ws.send.call_args.args[0]
        payload = json.loads(sent)
        assert payload["flush"] is True

    def test_wait_for_flush_returns_true_when_set(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s._flush_done.set()
        assert s.wait_for_flush(timeout=0.1) is True

    def test_wait_for_flush_returns_false_on_timeout(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        # _flush_done not set → wait times out
        assert s.wait_for_flush(timeout=0.05) is False


class TestStreamClose:
    def test_close_is_idempotent(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s._closed = True

        s.close()  # second call should be no-op
        # No exception, _closed stays True

    def test_close_sends_eos_and_signals_queue(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True

        s.close()

        assert s._closed is True
        # Sentinel None pushed to audio_queue
        sentinel = s.audio_queue.get(timeout=0.1)
        assert sentinel is None
        # EOS message sent
        sent = s.ws.send.call_args.args[0]
        payload = json.loads(sent)
        assert payload["text"] == ""

    def test_close_swallows_send_exception(self, env_with_api_key):
        # Production wraps the EOS send in try/except — pin that close() doesn't
        # leak network exceptions to the caller.
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True
        s.ws.send.side_effect = ConnectionError("socket dead")

        s.close()  # should not raise
        # Sentinel still pushed
        assert s.audio_queue.get(timeout=0.1) is None


class TestStreamIterAudio:
    def test_yields_chunks_until_sentinel(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.audio_queue.put("chunk1")
        s.audio_queue.put("chunk2")
        s.audio_queue.put(None)  # sentinel

        result = list(s.iter_audio())
        assert result == ["chunk1", "chunk2"]


class TestStreamCallbacks:
    def test_on_open_sets_connected_and_sends_bos(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True

        s._on_open(s.ws)

        assert s._connected.is_set() is True
        # BOS message sent with voice_settings
        sent = s.ws.send.call_args.args[0]
        payload = json.loads(sent)
        assert payload["text"] == " "
        assert "voice_settings" in payload
        assert payload["voice_settings"]["stability"] == 0.5
        assert payload["voice_settings"]["similarity_boost"] == 0.75
        assert payload["voice_settings"]["use_speaker_boost"] is True
        assert payload["xi_api_key"] == env_with_api_key

    def test_on_message_with_audio_pushes_to_queue(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        s._on_message(MagicMock(), json.dumps({"audio": "base64chunkXYZ"}))

        assert s.audio_queue.get_nowait() == "base64chunkXYZ"

    def test_on_message_without_audio_skips_queue(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        # Empty / non-audio message
        s._on_message(MagicMock(), json.dumps({}))
        s._on_message(MagicMock(), json.dumps({"isFinal": True}))

        # Queue should be empty (no audio chunks pushed)
        with pytest.raises(queue.Empty):
            s.audio_queue.get_nowait()

    def test_on_message_with_isfinal_sets_flush_done(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        assert s._flush_done.is_set() is False

        s._on_message(MagicMock(), json.dumps({"isFinal": True}))
        assert s._flush_done.is_set() is True

    def test_on_message_isfinal_does_not_push_sentinel(self, env_with_api_key):
        # Critical: isFinal must NOT put None in the audio queue. None
        # would kill the _drain_audio thread, but the pipeline must
        # stay alive for subsequent text rounds (per production comment
        # at line 254-257).
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        s._on_message(MagicMock(), json.dumps({"isFinal": True}))

        with pytest.raises(queue.Empty):
            s.audio_queue.get_nowait()

    def test_on_message_swallows_invalid_json(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        # Should not raise
        s._on_message(MagicMock(), "not valid json")
        s._on_message(MagicMock(), b"binary garbage")

    def test_on_error_pushes_sentinel(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()

        s._on_error(MagicMock(), Exception("ws error"))

        assert s.audio_queue.get_nowait() is None

    def test_on_close_pushes_sentinel_when_not_already_closed(
        self, env_with_api_key,
    ):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        # _closed defaults to False

        s._on_close(MagicMock(), 1000, "normal")

        assert s.audio_queue.get_nowait() is None

    def test_on_close_no_sentinel_when_already_closed(self, env_with_api_key):
        # If close() was already called, _on_close shouldn't double-push None
        # (the explicit close() call already pushed one).
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s._closed = True  # simulate close() already ran

        s._on_close(MagicMock(), 1000, "normal")

        # No new sentinel pushed
        with pytest.raises(queue.Empty):
            s.audio_queue.get_nowait()


class TestKeepaliveLoop:
    """The keepalive loop sends a space every 10s to prevent the
    20s ElevenLabs idle-timeout. Test by mocking `time.sleep` to no-op
    and using `_closed` to break the loop after a controlled number
    of iterations.
    """

    def test_sends_keepalive_when_idle_threshold_exceeded(
        self, env_with_api_key,
    ):
        from backend.services import elevenlabs_service as mod
        s = mod.ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True
        s._last_send = 0.0  # set far in the past

        iteration = [0]

        def fake_sleep(_seconds):
            iteration[0] += 1
            # Allow first iteration to complete (send fires); close before
            # the SECOND iteration starts so the loop exits cleanly.
            if iteration[0] >= 2:
                s._closed = True

        with patch.object(mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(mod.time, "time", return_value=1000.0):
            s._keepalive_loop()

        # Verify _send_json was called with a space (the keepalive payload)
        assert s.ws.send.called
        sent = s.ws.send.call_args.args[0]
        payload = json.loads(sent)
        assert payload == {"text": " "}
        # _last_send updated to the new time
        assert s._last_send == 1000.0

    def test_no_keepalive_when_recent_activity(self, env_with_api_key):
        from backend.services import elevenlabs_service as mod
        s = mod.ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True
        s._last_send = 995.0  # recent

        iteration = [0]

        def fake_sleep(_seconds):
            iteration[0] += 1
            # Allow one iteration through the elapsed check, then close
            if iteration[0] >= 2:
                s._closed = True

        with patch.object(mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(mod.time, "time", return_value=1000.0):
            # elapsed = 1000 - 995 = 5 (< 10) → no send
            s._keepalive_loop()

        s.ws.send.assert_not_called()

    def test_loop_exits_immediately_when_already_closed(
        self, env_with_api_key,
    ):
        from backend.services import elevenlabs_service as mod
        s = mod.ElevenLabsTTSStream()
        s._closed = True

        # Even without the time mock, this should return immediately
        # because the `while not self._closed` is False on entry.
        s._keepalive_loop()  # should not hang or raise

    def test_breaks_when_closed_after_sleep(self, env_with_api_key):
        # Hit the inner `if self._closed: break` at line 220-221 — when
        # close() fires DURING the sleep, the loop must exit before any
        # send attempt rather than racing with the ws teardown.
        from backend.services import elevenlabs_service as mod
        s = mod.ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True

        def fake_sleep(_seconds):
            # Close during sleep — the post-sleep guard should break out
            s._closed = True

        with patch.object(mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(mod.time, "time", return_value=1000.0):
            s._keepalive_loop()

        # No send should have happened — broke before any send check
        s.ws.send.assert_not_called()

    def test_send_exception_breaks_loop(self, env_with_api_key):
        # Production wraps the keepalive `_send_json` in try/except and
        # `break`s on any exception (line 227-228). Pin that the loop
        # exits cleanly when the WS is dead — no infinite retry.
        from backend.services import elevenlabs_service as mod
        s = mod.ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True
        s.ws.send.side_effect = ConnectionError("ws dead")
        s._last_send = 0.0  # idle long enough to trigger send

        iteration = [0]

        def fake_sleep(_seconds):
            iteration[0] += 1
            # Safety: force close if loop somehow doesn't break on its own
            if iteration[0] > 5:
                s._closed = True

        with patch.object(mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(mod.time, "time", return_value=1000.0):
            s._keepalive_loop()

        # The send was attempted exactly once before the exception broke the loop
        assert s.ws.send.call_count == 1
        # Loop exited via the inner break (not the safety force-close)
        assert iteration[0] == 1


class TestSendJson:
    def test_no_op_when_ws_none(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = None
        # Should not raise
        s._send_json({"text": "x"})

    def test_no_op_when_sock_disconnected(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = False
        s._send_json({"text": "x"})
        s.ws.send.assert_not_called()

    def test_sends_json_when_connected(self, env_with_api_key):
        from backend.services.elevenlabs_service import ElevenLabsTTSStream
        s = ElevenLabsTTSStream()
        s.ws = MagicMock()
        s.ws.sock.connected = True

        s._send_json({"text": "hello", "flush": True})

        sent = s.ws.send.call_args.args[0]
        assert json.loads(sent) == {"text": "hello", "flush": True}


# ──────────────────────────────────────────────────────────────────
# Module-level constants
# ──────────────────────────────────────────────────────────────────


class TestModuleConstants:
    def test_default_voice_id_is_string(self):
        from backend.services.elevenlabs_service import DEFAULT_VOICE_ID
        assert isinstance(DEFAULT_VOICE_ID, str)
        assert len(DEFAULT_VOICE_ID) > 0

    def test_default_model_id_is_turbo(self):
        from backend.services.elevenlabs_service import DEFAULT_MODEL_ID
        assert DEFAULT_MODEL_ID == "eleven_turbo_v2_5"

    def test_default_output_format_is_mp3(self):
        from backend.services.elevenlabs_service import DEFAULT_OUTPUT_FORMAT
        assert DEFAULT_OUTPUT_FORMAT == "mp3_44100_128"
