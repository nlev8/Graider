/**
 * Pure helpers for the useVoice hook (no React hook calls inside).
 * Bodies relocated verbatim from useVoice.js — Web Audio / SpeechRecognition
 * timing behavior must not change here.
 */

export const PRE_BUFFER_CHUNKS = 5
export const PRE_BUFFER_MS = 2000
export const SILENCE_TIMEOUT_MS = 4000

export function isSpeechRecognitionSupported() {
  return typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)
}

/** Build a configured SpeechRecognition instance for continuous dictation. */
export function createSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const recognition = new SpeechRecognition()
  recognition.continuous = true
  recognition.interimResults = true
  recognition.lang = 'en-US'
  return recognition
}

/**
 * Fold a SpeechRecognition result event into the accumulated transcript.
 * Returns the new accumulated (final results only) and the live display
 * transcript (accumulated + interim).
 */
export function accumulateTranscript(accumulated, event) {
  let finalTranscript = ''
  let interimTranscript = ''

  for (let i = event.resultIndex; i < event.results.length; i++) {
    if (event.results[i].isFinal) {
      finalTranscript += event.results[i][0].transcript
    } else {
      interimTranscript += event.results[i][0].transcript
    }
  }

  if (finalTranscript) {
    accumulated += (accumulated ? ' ' : '') + finalTranscript
  }

  // Show accumulated + interim as live transcript
  const live = accumulated + (interimTranscript ? ' ' + interimTranscript : '')
  return { accumulated, live: live.trim() }
}

/**
 * 'no-speech' and 'aborted' are normal in continuous mode — don't kill the
 * session. Everything else (not-allowed, service-not-allowed, network) is fatal.
 */
export function isFatalRecognitionError(errorCode) {
  return errorCode !== 'no-speech' && errorCode !== 'aborted'
}

/** Decode a base64 mp3 chunk into an ArrayBuffer for decodeAudioData. */
export function decodeBase64ToArrayBuffer(base64) {
  const binaryStr = atob(base64)
  const bytes = new Uint8Array(binaryStr.length)
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i)
  }
  return bytes.buffer.slice(0)
}

/**
 * Wait for the audio queue to receive a chunk.
 * If the SSE stream is still sending, wait longer for more chunks.
 * On slow connections (hotspot), TTS API calls can take 2-3s each,
 * so we need a generous window to avoid premature silence.
 * Resolves true if a chunk is available, false if the queue stayed empty.
 */
export async function waitForQueuedChunk({ getQueueLength, isStreamDone, retryDelayMs = 500 }) {
  const maxRetries = isStreamDone() ? 2 : 20
  for (let i = 0; i < maxRetries; i++) {
    await new Promise(r => setTimeout(r, retryDelayMs))
    if (getQueueLength() > 0) break
    if (isStreamDone()) break
  }
  return getQueueLength() > 0
}

/**
 * Poll `isDone` every `intervalMs` until it returns true or `maxChecks` is
 * exceeded. Resolves immediately if already done.
 */
export function pollUntil(isDone, { intervalMs = 200, maxChecks = 75 } = {}) {
  return new Promise(resolve => {
    if (isDone()) {
      resolve()
      return
    }
    let checks = 0
    const interval = setInterval(() => {
      checks++
      if (isDone() || checks > maxChecks) {
        clearInterval(interval)
        resolve()
      }
    }, intervalMs)
  })
}
