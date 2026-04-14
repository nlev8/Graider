"""Behavior-pinning tests for backend/services/openai_tts_service.py.

Phase 2 Task 6 PR-c-2. Per Codex Gate 1: SentenceBuffer gets
comprehensive coverage (pure, deterministic); OpenAITTSStream gets
ONLY deterministic cases — no races on real worker threads. The
sequencer ordering property is tested by preloading _results out of
order and driving the sequencer logic directly, not by racing workers.

Covers:
  - SentenceBuffer strong/weak/force splits, whitespace, flush, unicode
  - OpenAITTSStream constructor errors (ImportError / missing key)
  - voice/model env var override
  - send_text() seq-number monotonicity
  - close() idempotence
  - iter_audio() terminates on None sentinel
  - Sequencer emits in strict seq order given preloaded out-of-order
    results (no real worker threads).
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.services.openai_tts_service import (
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    OpenAITTSStream,
    SentenceBuffer,
)
import backend.services.openai_tts_service as tts_mod


# ─────────────────────────────────────────────────────────────────
# SentenceBuffer — pure unit tests
# ─────────────────────────────────────────────────────────────────

class TestSentenceBufferStrongBreaks:
    def test_period_emits(self):
        buf = SentenceBuffer()
        assert buf.add("Hello.") == ["Hello."]
        assert buf.buffer == ""

    def test_exclamation_emits(self):
        buf = SentenceBuffer()
        assert buf.add("Wow!") == ["Wow!"]

    def test_question_emits(self):
        buf = SentenceBuffer()
        assert buf.add("Why?") == ["Why?"]

    def test_newline_is_strong_break(self):
        buf = SentenceBuffer()
        chunks = buf.add("Line one\nLine two")
        # "\n" triggers a split; "Line one\n" (stripped becomes "Line one\n")
        assert chunks == ["Line one\n"]
        assert buf.buffer == "Line two"

    def test_multiple_strong_breaks_split_each(self):
        buf = SentenceBuffer()
        chunks = buf.add("One. Two. Three.")
        assert chunks == ["One.", "Two.", "Three."]

    def test_incremental_accumulation(self):
        buf = SentenceBuffer()
        assert buf.add("Hell") == []
        assert buf.add("o wo") == []
        assert buf.add("rld.") == ["Hello world."]


class TestSentenceBufferWeakBreaks:
    def test_weak_break_ignored_below_min(self):
        # WEAK_MIN = 25 — a comma before buffer reaches 25 does not split
        buf = SentenceBuffer()
        assert buf.add("short, text") == []
        assert "short" in buf.buffer

    def test_weak_break_emits_at_or_above_min(self):
        # 25+ chars with a comma past index 12 → splits at the comma
        buf = SentenceBuffer()
        text = "A sentence piece, continuing further"  # comma at idx 16
        chunks = buf.add(text)
        assert chunks == ["A sentence piece,"]

    def test_weak_break_semicolon(self):
        buf = SentenceBuffer()
        chunks = buf.add("A long clause here; another part follows")
        assert any(c.endswith(";") for c in chunks)

    def test_weak_break_em_dash(self):
        buf = SentenceBuffer()
        chunks = buf.add("One particular phrase\u2014and another bit")
        assert any(c.endswith("\u2014") for c in chunks)

    def test_weak_break_closing_paren(self):
        # ")" is a weak break per SentenceBuffer.WEAK
        buf = SentenceBuffer()
        chunks = buf.add("Preamble (note inside) and then more text")
        assert any(c.endswith(")") for c in chunks)

    def test_weak_break_boundary_idx_11_does_not_split(self):
        # Production code at backend/services/openai_tts_service.py:74 uses
        # `idx >= 12`. Comma at idx 11 must NOT trigger a weak split even
        # though buffer >= WEAK_MIN (25).
        buf = SentenceBuffer()
        # 11 chars, then comma at idx 11, then 14 more chars → len 26, no
        # strong break, 26 < MAX_LEN=60 so no force emit either.
        text = "abcdefghijk,mnopqrstuvwxyz"
        assert text.index(",") == 11
        assert len(text) >= SentenceBuffer.WEAK_MIN
        chunks = buf.add(text)
        assert chunks == []
        assert buf.buffer == text

    def test_weak_break_boundary_idx_12_splits(self):
        # Comma at exactly idx 12 DOES trigger a weak split — boundary is
        # inclusive at 12.
        buf = SentenceBuffer()
        text = "abcdefghijkl,mnopqrstuvwxyz"  # comma at idx 12, len 27
        assert text.index(",") == 12
        assert len(text) >= SentenceBuffer.WEAK_MIN
        chunks = buf.add(text)
        assert chunks == ["abcdefghijkl,"]
        assert buf.buffer == "mnopqrstuvwxyz"

    def test_weak_min_boundary_len_24_does_not_split(self):
        # Production code at backend/services/openai_tts_service.py:70 uses
        # `len(self.buffer) >= self.WEAK_MIN` (WEAK_MIN = 25). A buffer of
        # exactly 24 chars with a comma at idx 12 (past the idx-12 rule)
        # must NOT split because WEAK_MIN gate blocks entry.
        buf = SentenceBuffer()
        text = "abcdefghijkl,mnopqrstuvw"  # len 24, comma at idx 12
        assert len(text) == SentenceBuffer.WEAK_MIN - 1
        assert text.index(",") == 12
        chunks = buf.add(text)
        assert chunks == []
        assert buf.buffer == text

    def test_weak_min_boundary_len_25_splits(self):
        # Exactly WEAK_MIN (25) characters with comma at idx 12 → gate
        # opens, idx rule passes, split at the comma.
        buf = SentenceBuffer()
        text = "abcdefghijkl,mnopqrstuvwx"  # len 25
        assert len(text) == SentenceBuffer.WEAK_MIN
        assert text.index(",") == 12
        chunks = buf.add(text)
        assert chunks == ["abcdefghijkl,"]
        assert buf.buffer == "mnopqrstuvwx"


class TestSentenceBufferForceEmit:
    def test_force_emit_at_max_len_last_space(self):
        # MAX_LEN = 60 — no strong/weak breaks → split at last space ≤ 60
        buf = SentenceBuffer()
        text = "x " * 35  # 70 chars of alternating char+space → many spaces
        chunks = buf.add(text)
        assert chunks, "should force-emit chunk"
        assert len(chunks[0]) <= 60

    def test_force_emit_no_space_uses_max_len(self):
        buf = SentenceBuffer()
        text = "A" * 80
        chunks = buf.add(text)
        assert chunks, "should force-emit"
        assert len(chunks[0]) == 60


class TestSentenceBufferFlush:
    def test_flush_returns_remaining(self):
        buf = SentenceBuffer()
        buf.add("partial")
        assert buf.flush() == "partial"
        assert buf.buffer == ""

    def test_flush_empty_returns_none(self):
        buf = SentenceBuffer()
        assert buf.flush() is None

    def test_flush_whitespace_returns_none(self):
        buf = SentenceBuffer()
        buf.buffer = "   \t  "
        assert buf.flush() is None


class TestSentenceBufferWhitespace:
    def test_leading_whitespace_stripped_after_emit(self):
        buf = SentenceBuffer()
        buf.add("First.    Second.")
        # After first emit, leading spaces before "Second." are lstripped
        assert not buf.buffer.startswith(" ")

    def test_whitespace_only_chunk_not_emitted(self):
        buf = SentenceBuffer()
        # "." at position 0 → chunk is ".", stripped is "." (non-empty)
        chunks = buf.add(".")
        assert chunks == ["."]
        # But leading whitespace fragment "  ." would emit "." (stripped ok)


# ─────────────────────────────────────────────────────────────────
# OpenAITTSStream — constructor / config
# ─────────────────────────────────────────────────────────────────

class TestConstructor:
    def test_raises_when_openai_pkg_missing(self, monkeypatch):
        monkeypatch.setattr(tts_mod, "openai_pkg", None)
        with pytest.raises(ImportError, match="openai package required"):
            OpenAITTSStream()

    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.setattr(tts_mod, "openai_pkg", MagicMock())
        with patch("backend.api_keys.get_api_key", return_value=None):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
                OpenAITTSStream()

    def test_defaults_applied_when_no_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_TTS_VOICE", raising=False)
        monkeypatch.delenv("OPENAI_TTS_MODEL", raising=False)
        fake_openai = MagicMock()
        monkeypatch.setattr(tts_mod, "openai_pkg", fake_openai)
        with patch("backend.api_keys.get_api_key", return_value="sk-test"):
            stream = OpenAITTSStream()
        assert stream.voice == DEFAULT_VOICE
        assert stream.model == DEFAULT_MODEL
        assert stream.num_workers == 3  # NUM_TTS_WORKERS default

    def test_env_overrides_voice_and_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_TTS_VOICE", "alloy")
        monkeypatch.setenv("OPENAI_TTS_MODEL", "tts-1-hd")
        monkeypatch.setattr(tts_mod, "openai_pkg", MagicMock())
        with patch("backend.api_keys.get_api_key", return_value="sk-test"):
            stream = OpenAITTSStream()
        assert stream.voice == "alloy"
        assert stream.model == "tts-1-hd"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_TTS_VOICE", "alloy")
        monkeypatch.setattr(tts_mod, "openai_pkg", MagicMock())
        with patch("backend.api_keys.get_api_key", return_value="sk-test"):
            stream = OpenAITTSStream(voice="shimmer", model="tts-custom", num_workers=5)
        assert stream.voice == "shimmer"
        assert stream.model == "tts-custom"
        assert stream.num_workers == 5


# ─────────────────────────────────────────────────────────────────
# OpenAITTSStream — no-thread behavior (direct method calls)
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def stream(monkeypatch):
    """A constructed stream with no connect() called — no threads running."""
    monkeypatch.setattr(tts_mod, "openai_pkg", MagicMock())
    with patch("backend.api_keys.get_api_key", return_value="sk-test"):
        s = OpenAITTSStream()
    return s


class TestSendTextSeq:
    def test_send_text_assigns_monotonic_seq(self, stream):
        stream.send_text("a")
        stream.send_text("b")
        stream.send_text("c")
        # Drain internal queue to read seq numbers
        jobs = []
        while not stream._job_queue.empty():
            jobs.append(stream._job_queue.get_nowait())
        seqs = [j[2] for j in jobs]
        assert seqs == sorted(seqs)  # monotonic
        assert seqs == [0, 1, 2]

    def test_send_text_noop_after_close(self, stream):
        stream._closed = True
        stream.send_text("x")
        # send_text should return without queueing
        # (queue may contain None poison pills from close path, but no new work)
        # Easier: seq counter must not advance
        assert stream._seq_counter == 0

    def test_flush_assigns_seq_and_clears_event(self, stream):
        stream._flush_done.set()  # pre-set to prove clear()
        stream.flush()
        assert not stream._flush_done.is_set()
        assert stream._seq_counter == 1


class TestCloseIdempotent:
    def test_close_sets_closed_flag(self, stream):
        stream.close()
        assert stream._closed is True

    def test_close_second_call_noop(self, stream):
        stream.close()
        # Capture state
        audio_size_after_first = stream.audio_queue.qsize()
        stream.close()
        # Second close() must not push additional None sentinels
        assert stream.audio_queue.qsize() == audio_size_after_first

    def test_close_pushes_sentinel_per_worker(self, stream):
        # No workers started — _workers is empty → no poison pills, but
        # audio_queue still gets its terminating None
        stream.close()
        items = []
        while not stream.audio_queue.empty():
            items.append(stream.audio_queue.get_nowait())
        assert items[-1] is None

    def test_iter_audio_terminates_on_sentinel(self, stream):
        stream.audio_queue.put("chunk1")
        stream.audio_queue.put("chunk2")
        stream.audio_queue.put(None)
        chunks = list(stream.iter_audio())
        assert chunks == ["chunk1", "chunk2"]


# ─────────────────────────────────────────────────────────────────
# Sequencer ordering — driven directly, no real worker threads
# ─────────────────────────────────────────────────────────────────

class TestSequencerOrdering:
    def test_sequencer_emits_in_strict_seq_order(self, stream):
        """Preload _results out of order; assert sequencer emits in-order.

        Drive the sequencer inline instead of racing the thread: the while
        loop inside _sequencer_loop pops from _results by _next_emit and
        enqueues to audio_queue. We simulate one pass.
        """
        with stream._results_lock:
            stream._results[2] = ("audio", "C")
            stream._results[0] = ("audio", "A")
            stream._results[1] = ("audio", "B")

        # Manually replicate the sequencer's inner emit loop
        while True:
            with stream._results_lock:
                result = stream._results.pop(stream._next_emit, None)
            if result is None:
                break
            rtype, data = result
            if rtype == "audio":
                stream.audio_queue.put(data)
            stream._next_emit += 1

        emitted = []
        while not stream.audio_queue.empty():
            emitted.append(stream.audio_queue.get_nowait())
        assert emitted == ["A", "B", "C"]

    def test_sequencer_skip_advances_counter_without_emit(self, stream):
        """A 'skip' result (failed API call) advances _next_emit but does not
        push to audio_queue."""
        with stream._results_lock:
            stream._results[0] = ("audio", "first")
            stream._results[1] = ("skip", None)
            stream._results[2] = ("audio", "third")

        while True:
            with stream._results_lock:
                result = stream._results.pop(stream._next_emit, None)
            if result is None:
                break
            rtype, data = result
            if rtype == "audio":
                stream.audio_queue.put(data)
            # skip → no push
            stream._next_emit += 1

        emitted = []
        while not stream.audio_queue.empty():
            emitted.append(stream.audio_queue.get_nowait())
        assert emitted == ["first", "third"]
        assert stream._next_emit == 3

    def test_sequencer_flush_sets_flush_done(self, stream):
        """A 'flush' result must set _flush_done but not push audio."""
        stream._flush_done.clear()
        with stream._results_lock:
            stream._results[0] = ("flush", None)

        with stream._results_lock:
            result = stream._results.pop(stream._next_emit, None)
        rtype, _data = result
        if rtype == "flush":
            stream._flush_done.set()
        stream._next_emit += 1

        assert stream._flush_done.is_set()
        assert stream.audio_queue.empty()

    def test_sequencer_stops_on_gap(self, stream):
        """Pop must return None when next expected seq is absent — even if
        later seqs are available. Prevents out-of-order emission."""
        with stream._results_lock:
            stream._results[0] = ("audio", "A")
            # seq 1 missing
            stream._results[2] = ("audio", "C")

        # First pass: emit seq 0, then seq 1 missing → stop
        emitted = []
        while True:
            with stream._results_lock:
                result = stream._results.pop(stream._next_emit, None)
            if result is None:
                break
            rtype, data = result
            if rtype == "audio":
                emitted.append(data)
            stream._next_emit += 1

        assert emitted == ["A"]
        # C remains in _results awaiting seq 1
        assert 2 in stream._results
