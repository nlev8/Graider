"""
ElevenLabs Text-to-Speech Streaming Service
============================================
WebSocket client for real-time TTS via ElevenLabs API.
Receives text chunks, returns base64 mp3 audio chunks.
"""

import os
import json
import time
import threading
import queue
import logging

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID = "UgBBYS2sOqTuMpoF3BR0"
DEFAULT_MODEL_ID = "eleven_turbo_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


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
    WEAK_MIN = 30  # Only split on weak break if buffer >= this many chars
    MAX_LEN = 80   # Force-emit if buffer exceeds this, splitting at last space

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
                    if idx != -1 and idx >= 15 and (earliest == -1 or idx < earliest):
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


class ElevenLabsTTSStream:
    """Manages a WebSocket connection to ElevenLabs for streaming TTS.

    Usage:
        stream = ElevenLabsTTSStream()
        stream.connect()
        stream.send_text("Hello world. ")
        for audio_b64 in stream.iter_audio():
            # audio_b64 is a base64-encoded mp3 chunk
            pass
        stream.close()
    """

    def __init__(self, voice_id=None, model_id=None):
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")

        self.api_key = api_key
        self.voice_id = (
            voice_id
            or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        )
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.audio_queue = queue.Queue()
        self.ws = None
        self._closed = False
        self._connected = threading.Event()
        self._flush_done = threading.Event()

    def connect(self):
        """Open the ElevenLabs WebSocket connection."""
        if websocket is None:
            raise ImportError(
                "websocket-client required: pip install websocket-client"
            )

        url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.voice_id}/stream-input"
            f"?model_id={self.model_id}"
            f"&output_format={DEFAULT_OUTPUT_FORMAT}"
        )

        self.ws = websocket.WebSocketApp(
            url,
            header={"xi-api-key": self.api_key},
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        thread = threading.Thread(
            target=self.ws.run_forever, daemon=True
        )
        thread.start()

        # Wait for connection to establish
        if not self._connected.wait(timeout=5.0):
            raise ConnectionError(
                "ElevenLabs WebSocket connection timed out"
            )

        # Start keep-alive thread to prevent 20s timeout during tool calls
        self._last_send = time.time()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop, daemon=True
        )
        self._keepalive_thread.start()

    def send_text(self, text):
        """Send a text chunk for TTS conversion."""
        if self._closed or not self.ws:
            return
        self._last_send = time.time()
        self._send_json({
            "text": text,
            "try_trigger_generation": True,
        })

    def flush(self):
        """Force generation of any remaining buffered text."""
        if self._closed or not self.ws:
            return
        self._flush_done.clear()
        self._last_send = time.time()
        self._send_json({"text": " ", "flush": True})

    def wait_for_flush(self, timeout=5.0):
        """Block until ElevenLabs finishes generating audio for the flushed text.
        Returns True if flush completed, False on timeout."""
        return self._flush_done.wait(timeout=timeout)

    def close(self):
        """Send end-of-stream signal and close."""
        if self._closed:
            return
        self._closed = True
        try:
            self._send_json({"text": ""})  # EOS
        except Exception:
            pass
        self.audio_queue.put(None)

    def iter_audio(self):
        """Yield base64 mp3 audio chunks. Blocks until available."""
        while True:
            chunk = self.audio_queue.get()
            if chunk is None:
                break
            yield chunk

    def _keepalive_loop(self):
        """Send a space every 15s to prevent ElevenLabs 20s idle timeout."""
        while not self._closed:
            time.sleep(5)
            if self._closed:
                break
            elapsed = time.time() - self._last_send
            if elapsed >= 15:
                try:
                    self._send_json({"text": " "})
                    self._last_send = time.time()
                except Exception:
                    break

    def _send_json(self, data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(data))

    def _on_open(self, ws):
        self._connected.set()
        # Send BOS (beginning of stream) with voice settings
        self._send_json({
            "text": " ",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
            "xi_api_key": self.api_key,
        })

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            audio = data.get("audio")
            if audio:
                self.audio_queue.put(audio)
            if data.get("isFinal"):
                # Signal that flush/generation is complete — but do NOT put None
                # in the queue. None kills the _drain_audio thread permanently.
                # The pipeline must stay alive for subsequent text rounds.
                self._flush_done.set()
        except Exception:
            pass

    def _on_error(self, ws, error):
        logger.error("ElevenLabs WS error: %s", error)
        self.audio_queue.put(None)

    def _on_close(self, ws, close_status, close_msg):
        if not self._closed:
            self.audio_queue.put(None)
