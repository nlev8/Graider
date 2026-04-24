"""Tests for _finalize_assistant_stream idempotency + disconnect behavior.

Phase 5b PR 4.
"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_finalize_idempotency_concurrent_reentrance():
    """If session_id is already in _finalizing_sessions, the second call
    is a silent no-op (yields nothing, touches no side effects)."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()
    assistant_routes._finalizing_sessions.add("session-X")

    tts_stream = MagicMock()

    gen = assistant_routes._finalize_assistant_stream(
        session_id="session-X",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream,
        sentence_buffer=MagicMock(),
        audio_out_queue=MagicMock(),
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=False,
    )

    yields = list(gen)
    assert yields == []
    tts_stream.close.assert_not_called()
    tts_stream.flush.assert_not_called()

    assistant_routes._finalizing_sessions.clear()


def test_finalize_releases_session_on_completion():
    """After normal completion, session_id is removed from the set so a
    subsequent independent request can run its own finalizer."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()

    tts_stream = MagicMock()
    audio_queue = MagicMock()
    audio_queue.get.return_value = None  # immediate exit from drain loop

    gen = assistant_routes._finalize_assistant_stream(
        session_id="session-Y",
        conv={"messages": ["initial"]},
        messages=["initial"],
        tts_stream=tts_stream,
        sentence_buffer=None,
        audio_out_queue=audio_queue,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=False,
    )

    list(gen)

    assert "session-Y" not in assistant_routes._finalizing_sessions


def test_finalize_disconnect_mode_skips_wait_for_flush():
    """In disconnect mode (cancelled=True), tts_stream.wait_for_flush
    must NOT be called. close() is still called."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()

    tts_stream = MagicMock()

    gen = assistant_routes._finalize_assistant_stream(
        session_id="session-Z",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream,
        sentence_buffer=None,
        audio_out_queue=MagicMock(),
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=True,
    )

    list(gen)

    tts_stream.wait_for_flush.assert_not_called()
    tts_stream.close.assert_called_once()


def test_finalize_silent_wrapper_discards_yields():
    """_finalize_assistant_stream_silent runs the helper but discards yields
    (for the GeneratorExit path where yield-from is illegal)."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()

    tts_stream = MagicMock()
    audio_queue = MagicMock()
    audio_queue.get.return_value = None

    # Should not raise, should not yield anything (it's not a generator)
    result = assistant_routes._finalize_assistant_stream_silent(
        session_id="session-W",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream,
        sentence_buffer=None,
        audio_out_queue=audio_queue,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=True,
    )
    assert result is None
    # Still ran state cleanup
    tts_stream.close.assert_called_once()


def test_finalize_reentrance_during_active_run_is_silent_noop():
    """Simulate the race: normal-completion's yield-from is mid-drain
    when client disconnects. Outer except GeneratorExit calls
    _finalize_assistant_stream_silent() — if session_id is still in
    _finalizing_sessions (guard held), the silent wrapper is a no-op."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()
    # Guard held — simulates the inner finalizer still running.
    assistant_routes._finalizing_sessions.add("session-RACE")

    tts_stream = MagicMock()
    audio_queue = MagicMock()
    audio_queue.get.return_value = None

    # Silent wrapper called while guard is held — should no-op entirely.
    assistant_routes._finalize_assistant_stream_silent(
        session_id="session-RACE",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream,
        sentence_buffer=None,
        audio_out_queue=audio_queue,
        total_input_tokens=100,
        total_output_tokens=50,
        total_tts_chars=500,
        active_model="gpt-4o",
        cancelled=True,
    )

    # Re-entrance guard short-circuited — zero side effects from the silent call
    tts_stream.close.assert_not_called()
    tts_stream.wait_for_flush.assert_not_called()

    # Guard unchanged (still held by the "active" finalizer)
    assert "session-RACE" in assistant_routes._finalizing_sessions

    assistant_routes._finalizing_sessions.clear()


def test_finalize_after_first_completion_second_call_runs_independently():
    """After the first finalizer completes (guard released in its finally),
    a second call with the same session_id is NOT a no-op — it represents
    a new independent request reusing the session ID."""
    from backend.routes import assistant_routes

    assistant_routes._finalizing_sessions.clear()

    tts_stream_a = MagicMock()
    audio_queue = MagicMock()
    audio_queue.get.return_value = None

    # First call — runs to completion
    list(assistant_routes._finalize_assistant_stream(
        session_id="session-SEQ",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream_a,
        sentence_buffer=None,
        audio_out_queue=audio_queue,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=False,
    ))

    assert "session-SEQ" not in assistant_routes._finalizing_sessions
    tts_stream_a.close.assert_called_once()

    # Second call — fresh tts_stream, same session_id. Should run normally
    # because the guard released session_id after first call's finally.
    tts_stream_b = MagicMock()
    list(assistant_routes._finalize_assistant_stream(
        session_id="session-SEQ",
        conv={"messages": []},
        messages=[],
        tts_stream=tts_stream_b,
        sentence_buffer=None,
        audio_out_queue=audio_queue,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tts_chars=0,
        active_model="gpt-4o",
        cancelled=False,
    ))

    # Second call ran independently
    tts_stream_b.close.assert_called_once()
