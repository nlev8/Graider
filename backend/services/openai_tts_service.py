"""
OpenAI Text-to-Speech Service
==============================
REST-based TTS using OpenAI's audio.speech.create API.
Receives text sentences, returns base64 MP3 audio chunks.
Drop-in replacement for ElevenLabsTTSStream with identical interface.

Uses a pool of concurrent workers to overlap API calls, reducing
stalls on high-latency connections (e.g. mobile hotspots).
"""

import os
import base64
import threading
import queue
import logging

try:
    import openai as openai_pkg
except ImportError:
    openai_pkg = None

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "nova"
DEFAULT_MODEL = "tts-1"
NUM_TTS_WORKERS = 3  # Concurrent API calls to overlap latency


class SentenceBuffer:
    """Accumulates text fragments and emits at natural speech boundaries.

    Emits on sentence endings (.!?), clause boundaries (,;:—),
    newlines, and when the buffer exceeds MAX_LEN characters.
    This keeps audio flowing smoothly without long gaps.
    """

    # Strong breaks — always split here
    STRONG = {'.', '!', '?', '\n'}
    # Weak breaks — split here if buffer is long enough for natural speech
    WEAK = {',', ';', ':', '\u2014', '\u2013', ')'}
    WEAK_MIN = 25  # Only split on weak break if buffer >= this many chars
    MAX_LEN = 60   # Force-emit if buffer exceeds this, splitting at last space

    def __init__(self):
        self.buffer = ""

    def add(self, text):
        """Add text and return list of speakable chunks."""
        self.buffer += text
        chunks = []

        while True:
            emitted = False

            # 1. Check for strong break (sentence ending)
            earliest = -1
            for ch in self.STRONG:
                idx = self.buffer.find(ch)
                if idx != -1 and (earliest == -1 or idx < earliest):
                    earliest = idx
            if earliest != -1:
                chunk = self.buffer[:earliest + 1]
                self.buffer = self.buffer[earliest + 1:].lstrip()
                if chunk.strip():
                    chunks.append(chunk)
                emitted = True

            # 2. Check for weak break (comma, semicolon) if buffer is long enough
            if not emitted and len(self.buffer) >= self.WEAK_MIN:
                earliest = -1
                for ch in self.WEAK:
                    idx = self.buffer.find(ch)
                    if idx != -1 and idx >= 12 and (earliest == -1 or idx < earliest):
                        earliest = idx
                if earliest != -1:
                    chunk = self.buffer[:earliest + 1]
                    self.buffer = self.buffer[earliest + 1:].lstrip()
                    if chunk.strip():
                        chunks.append(chunk)
                    emitted = True

            # 3. Force-emit on max length (split at last space)
            if not emitted and len(self.buffer) >= self.MAX_LEN:
                split_at = self.buffer.rfind(' ', 0, self.MAX_LEN)
                if split_at <= 0:
                    split_at = self.MAX_LEN
                chunk = self.buffer[:split_at]
                self.buffer = self.buffer[split_at:].lstrip()
                if chunk.strip():
                    chunks.append(chunk)
                emitted = True

            if not emitted:
                break

        return chunks

    def flush(self):
        """Return any remaining buffered text."""
        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining if remaining else None


class OpenAITTSStream:
    """Manages TTS generation using OpenAI's audio.speech.create API.

    Uses a pool of concurrent worker threads to overlap API latency.
    A sequencer ensures audio chunks are emitted in the correct order
    even when workers finish out of order.

    Same public interface as ElevenLabsTTSStream for drop-in replacement.

    Usage:
        stream = OpenAITTSStream()
        stream.connect()
        stream.send_text("Hello world. ")
        for audio_b64 in stream.iter_audio():
            # audio_b64 is a base64-encoded MP3 chunk
            pass
        stream.close()
    """

    def __init__(self, voice=None, model=None, num_workers=None):
        if openai_pkg is None:
            raise ImportError("openai package required: pip install openai")

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = openai_pkg.OpenAI(api_key=api_key)
        self.voice = (
            voice
            or os.environ.get("OPENAI_TTS_VOICE", DEFAULT_VOICE)
        )
        self.model = model or os.environ.get("OPENAI_TTS_MODEL", DEFAULT_MODEL)
        self.num_workers = num_workers or NUM_TTS_WORKERS
        self.audio_queue = queue.Queue()
        self._job_queue = queue.Queue()
        self._closed = False
        self._flush_done = threading.Event()
        self._workers = []

        # Sequencer: workers place results keyed by sequence number,
        # the sequencer thread emits them in order to audio_queue
        self._seq_counter = 0
        self._seq_lock = threading.Lock()
        self._results = {}       # seq_num -> base64 audio (or None for flush)
        self._results_lock = threading.Lock()
        self._results_ready = threading.Event()
        self._next_emit = 0
        self._sequencer_thread = None

    def connect(self):
        """Start worker threads and the sequencer."""
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"tts-worker-{i}")
            t.start()
            self._workers.append(t)

        self._sequencer_thread = threading.Thread(target=self._sequencer_loop, daemon=True, name="tts-sequencer")
        self._sequencer_thread.start()

    def send_text(self, text):
        """Queue a sentence for TTS conversion."""
        if self._closed:
            return
        with self._seq_lock:
            seq = self._seq_counter
            self._seq_counter += 1
        self._job_queue.put(("text", text, seq))

    def flush(self):
        """Signal end-of-segment, clears flush event."""
        if self._closed:
            return
        self._flush_done.clear()
        with self._seq_lock:
            seq = self._seq_counter
            self._seq_counter += 1
        self._job_queue.put(("flush", None, seq))

    def wait_for_flush(self, timeout=5.0):
        """Block until all queued text is processed.
        Returns True if flush completed, False on timeout."""
        return self._flush_done.wait(timeout=timeout)

    def close(self):
        """Stop workers and signal end of audio stream."""
        if self._closed:
            return
        self._closed = True
        # Send poison pills — one per worker
        for _ in self._workers:
            self._job_queue.put(None)
        # Wake sequencer so it can exit
        self._results_ready.set()
        self.audio_queue.put(None)

    def iter_audio(self):
        """Yield base64 MP3 audio chunks. Blocks until available."""
        while True:
            chunk = self.audio_queue.get()
            if chunk is None:
                break
            yield chunk

    def _worker_loop(self):
        """Pull jobs from the queue, call OpenAI TTS, deposit results by seq number."""
        while not self._closed:
            try:
                item = self._job_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if item is None:
                break

            msg_type, payload, seq_num = item

            if msg_type == "flush":
                with self._results_lock:
                    self._results[seq_num] = ("flush", None)
                self._results_ready.set()
                continue

            if msg_type == "text":
                text = payload.strip()
                if not text:
                    with self._results_lock:
                        self._results[seq_num] = ("skip", None)
                    self._results_ready.set()
                    continue
                try:
                    response = self.client.audio.speech.create(
                        model=self.model,
                        voice=self.voice,
                        input=text,
                        response_format="mp3",
                    )
                    mp3_bytes = response.content
                    b64_audio = base64.b64encode(mp3_bytes).decode("ascii")
                    with self._results_lock:
                        self._results[seq_num] = ("audio", b64_audio)
                except Exception as e:
                    logger.error("OpenAI TTS error for text '%s...': %s", text[:40], e)
                    with self._results_lock:
                        self._results[seq_num] = ("skip", None)
                self._results_ready.set()

    def _sequencer_loop(self):
        """Emit results to audio_queue in strict sequence order."""
        while not self._closed:
            self._results_ready.wait(timeout=1.0)
            self._results_ready.clear()

            # Emit as many consecutive results as are available
            while True:
                with self._results_lock:
                    result = self._results.pop(self._next_emit, None)
                if result is None:
                    break

                rtype, data = result
                if rtype == "audio":
                    self.audio_queue.put(data)
                elif rtype == "flush":
                    self._flush_done.set()
                # "skip" — just advance the counter

                self._next_emit += 1
