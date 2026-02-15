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

DEFAULT_VOICE_ID = "Aa6nEBJJMKJwJkCx8VU2"
DEFAULT_MODEL_ID = "eleven_turbo_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


class SentenceBuffer:
    """Accumulates text fragments and emits complete sentences.

    ElevenLabs produces better audio from complete sentences
    rather than tiny word fragments from streaming deltas.
    """

    ENDINGS = {'.', '!', '?', ':', '\n'}

    def __init__(self):
        self.buffer = ""

    def add(self, text):
        """Add text and return list of complete sentences."""
        self.buffer += text
        sentences = []

        while True:
            earliest = -1
            for ch in self.ENDINGS:
                idx = self.buffer.find(ch)
                if idx != -1 and (earliest == -1 or idx < earliest):
                    earliest = idx

            if earliest == -1:
                break

            sentence = self.buffer[:earliest + 1]
            self.buffer = self.buffer[earliest + 1:].lstrip()
            if sentence.strip():
                sentences.append(sentence)

        return sentences

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

    def send_text(self, text):
        """Send a text chunk for TTS conversion."""
        if self._closed or not self.ws:
            return
        self._send_json({
            "text": text,
            "try_trigger_generation": True,
        })

    def flush(self):
        """Force generation of any remaining buffered text."""
        if self._closed or not self.ws:
            return
        self._send_json({"text": " ", "flush": True})

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
                self.audio_queue.put(None)
        except Exception:
            pass

    def _on_error(self, ws, error):
        logger.error("ElevenLabs WS error: %s", error)
        self.audio_queue.put(None)

    def _on_close(self, ws, close_status, close_msg):
        if not self._closed:
            self.audio_queue.put(None)
