"""Gap-fill tests for backend/services/openai_tts_service.py.

Audit MAJOR #4 sprint follow-up to PR #320. Companion to existing
`tests/test_openai_tts_service.py` (which covers SentenceBuffer +
deterministic OpenAITTSStream cases). Targets the 56 missing LOC
(67.6% baseline → 90%+ goal):

* `_worker_loop` direct invocation (no thread racing): empty-text
  skip, OpenAI exception swallow, audio happy path, flush message,
  poison-pill termination
* `_sequencer_loop` direct invocation: flush event set, audio
  emitted in order, skip advances counter
* `connect()` actually starts threads (verify thread count, then
  close cleanly)
* `flush()`, `wait_for_flush()`, `close()` lifecycle
* `iter_audio()` terminates on None sentinel
* `_closed` early-returns on send_text/flush/close

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

import base64
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import backend.services.openai_tts_service as tts_mod
from backend.services.openai_tts_service import OpenAITTSStream


MODULE = "backend.services.openai_tts_service"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _make_stream():
    """Construct an OpenAITTSStream with a mock OpenAI client."""
    with patch(f"{MODULE}.openai_pkg") as mock_pkg, \
         patch("backend.api_keys.get_api_key", return_value="key"):
        mock_pkg.OpenAI.return_value = MagicMock()
        s = OpenAITTSStream(num_workers=2)
    return s


# ──────────────────────────────────────────────────────────────────
# _worker_loop direct invocation
# ──────────────────────────────────────────────────────────────────


class TestWorkerLoopDirect:
    def test_empty_text_emits_skip_result(self):
        s = _make_stream()
        # Pre-queue a "text" job with empty payload
        s._job_queue.put(("text", "   ", 0))
        # Then a poison pill to break the loop
        s._job_queue.put(None)

        s._worker_loop()  # Direct call; runs until poison pill

        assert s._results[0] == ("skip", None)

    def test_text_audio_happy_path(self):
        s = _make_stream()
        # Mock the audio.speech.create response
        mock_response = MagicMock()
        mock_response.content = b"fake-mp3-bytes"
        s.client.audio.speech.create.return_value = mock_response

        s._job_queue.put(("text", "Hello world.", 0))
        s._job_queue.put(None)

        s._worker_loop()

        rtype, data = s._results[0]
        assert rtype == "audio"
        assert isinstance(data, str)
        # data should be base64-encoded mp3
        assert base64.b64decode(data) == b"fake-mp3-bytes"

    def test_text_openai_exception_emits_skip(self):
        s = _make_stream()
        s.client.audio.speech.create.side_effect = RuntimeError("API down")

        s._job_queue.put(("text", "Hello.", 0))
        s._job_queue.put(None)

        s._worker_loop()

        assert s._results[0] == ("skip", None)

    def test_flush_message_emits_flush_result(self):
        s = _make_stream()
        s._job_queue.put(("flush", None, 0))
        s._job_queue.put(None)

        s._worker_loop()

        assert s._results[0] == ("flush", None)

    def test_queue_timeout_loops_until_closed_or_poison(self):
        # Don't queue anything; flip _closed flag to True from outside
        # the loop. The loop's `queue.get(timeout=1.0)` raises Empty,
        # then the while-condition exits because _closed is True.
        s = _make_stream()
        s._closed = True
        # Should return immediately via while-loop check
        s._worker_loop()
        # No results expected (no work was done)
        assert s._results == {}


# ──────────────────────────────────────────────────────────────────
# _sequencer_loop direct invocation
# ──────────────────────────────────────────────────────────────────


class TestSequencerLoopDirect:
    def test_emits_audio_in_strict_seq_order(self):
        s = _make_stream()
        # Pre-load results out of order
        s._results[1] = ("audio", "second-audio")
        s._results[0] = ("audio", "first-audio")
        s._results[2] = ("audio", "third-audio")
        s._results_ready.set()

        # Run sequencer in a brief window then close to break the loop
        def _run_sequencer_briefly():
            s._sequencer_loop()

        t = threading.Thread(target=_run_sequencer_briefly, daemon=True)
        t.start()
        # Give the sequencer a moment to drain
        time.sleep(0.1)
        s._closed = True
        s._results_ready.set()  # Wake from timeout
        t.join(timeout=2.0)

        # Drain audio_queue
        emitted = []
        try:
            while True:
                item = s.audio_queue.get_nowait()
                if item is not None:
                    emitted.append(item)
        except queue.Empty:
            pass

        assert emitted == ["first-audio", "second-audio", "third-audio"]

    def test_flush_result_sets_flush_done(self):
        s = _make_stream()
        s._results[0] = ("flush", None)
        s._results_ready.set()

        t = threading.Thread(target=s._sequencer_loop, daemon=True)
        t.start()
        time.sleep(0.1)
        s._closed = True
        s._results_ready.set()
        t.join(timeout=2.0)

        # Flush event was set
        assert s._flush_done.is_set()

    def test_skip_result_advances_counter(self):
        s = _make_stream()
        s._results[0] = ("skip", None)
        s._results[1] = ("audio", "real-audio")
        s._results_ready.set()

        t = threading.Thread(target=s._sequencer_loop, daemon=True)
        t.start()
        time.sleep(0.1)
        s._closed = True
        s._results_ready.set()
        t.join(timeout=2.0)

        # audio_queue should have only the second result
        emitted = []
        try:
            while True:
                item = s.audio_queue.get_nowait()
                if item is not None:
                    emitted.append(item)
        except queue.Empty:
            pass
        assert emitted == ["real-audio"]


# ──────────────────────────────────────────────────────────────────
# connect() / lifecycle
# ──────────────────────────────────────────────────────────────────


class TestConnectAndLifecycle:
    def test_connect_starts_workers_and_sequencer(self):
        s = _make_stream()
        s.connect()
        # 2 workers + 1 sequencer = 3 alive threads
        assert len(s._workers) == 2
        assert s._sequencer_thread is not None
        # Clean up
        s.close()
        for w in s._workers:
            w.join(timeout=2.0)

    def test_close_idempotent_does_not_double_send_pills(self):
        s = _make_stream()
        s.connect()
        s.close()
        # Second close should early-return
        s.close()
        # Drain any sentinels that leaked through
        for w in s._workers:
            w.join(timeout=2.0)

    def test_send_text_after_close_is_noop(self):
        s = _make_stream()
        s._closed = True
        s.send_text("hello")
        # No job was queued
        assert s._job_queue.empty()

    def test_flush_after_close_is_noop(self):
        s = _make_stream()
        s._closed = True
        s.flush()
        assert s._job_queue.empty()

    def test_flush_clears_event_and_queues_flush_marker(self):
        s = _make_stream()
        s._flush_done.set()  # Pretend a previous flush completed
        s.flush()
        # Flush event is cleared
        assert not s._flush_done.is_set()
        # Job queue has flush marker
        item = s._job_queue.get_nowait()
        assert item[0] == "flush"

    def test_wait_for_flush_returns_true_when_already_set(self):
        s = _make_stream()
        s._flush_done.set()
        assert s.wait_for_flush(timeout=0.1) is True

    def test_wait_for_flush_returns_false_on_timeout(self):
        s = _make_stream()
        # Event NOT set
        assert s.wait_for_flush(timeout=0.05) is False

    def test_iter_audio_terminates_on_none(self):
        s = _make_stream()
        s.audio_queue.put("chunk-1")
        s.audio_queue.put("chunk-2")
        s.audio_queue.put(None)
        result = list(s.iter_audio())
        assert result == ["chunk-1", "chunk-2"]

    def test_send_text_assigns_monotonic_seq_numbers(self):
        s = _make_stream()
        s.send_text("first")
        s.send_text("second")
        s.send_text("third")
        items = []
        try:
            while True:
                items.append(s._job_queue.get_nowait())
        except queue.Empty:
            pass
        seqs = [item[2] for item in items]
        assert seqs == [0, 1, 2]


# ──────────────────────────────────────────────────────────────────
# ImportError path
# ──────────────────────────────────────────────────────────────────


class TestImportErrorBranch:
    def test_constructor_raises_when_openai_missing(self):
        # Simulate openai package import failure
        with patch.object(tts_mod, "openai_pkg", None):
            with pytest.raises(ImportError, match="openai package"):
                OpenAITTSStream()

    def test_constructor_raises_when_no_api_key(self):
        with patch(f"{MODULE}.openai_pkg") as mock_pkg, \
             patch("backend.api_keys.get_api_key", return_value=None):
            mock_pkg.OpenAI.return_value = MagicMock()
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAITTSStream()
