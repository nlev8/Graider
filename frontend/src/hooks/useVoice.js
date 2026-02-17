import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * Hook for voice conversation in the assistant.
 * STT: Web Speech API (browser-native, free)
 * TTS: Audio playback from ElevenLabs base64 mp3 chunks
 */
export function useVoice({ onTranscript }) {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')

  const recognitionRef = useRef(null)
  const silenceTimerRef = useRef(null)
  const accumulatedRef = useRef('')
  const isListeningRef = useRef(false)
  const intentionalStopRef = useRef(false)
  const audioContextRef = useRef(null)
  const audioQueueRef = useRef([])
  const isPlayingRef = useRef(false)
  const sourceNodeRef = useRef(null)
  const bufferingRef = useRef(true)
  const bufferTimerRef = useRef(null)
  const streamDoneRef = useRef(false)
  const PRE_BUFFER_CHUNKS = 5
  const PRE_BUFFER_MS = 2000
  const SILENCE_TIMEOUT_MS = 4000

  // Keep ref in sync for use in callbacks
  useEffect(() => { isListeningRef.current = isListening }, [isListening])

  const speechAvailable = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
    }
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume()
    }
    return audioContextRef.current
  }, [])

  // ---- STT: Web Speech API ----

  const startListening = useCallback(() => {
    if (!speechAvailable) return

    // Clean up any existing recognition first
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (e) { /* */ }
      recognitionRef.current = null
    }

    accumulatedRef.current = ''
    intentionalStopRef.current = false

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'

    // Reset silence timer whenever speech activity occurs
    const resetSilenceTimer = () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = setTimeout(() => {
        // Silence detected — submit accumulated transcript and stop
        intentionalStopRef.current = true
        const text = accumulatedRef.current.trim()
        if (text) {
          onTranscript(text)
        }
        accumulatedRef.current = ''
        setTranscript('')
        if (recognitionRef.current) {
          try { recognitionRef.current.stop() } catch (e) { /* already stopped */ }
          recognitionRef.current = null
        }
        setIsListening(false)
      }, SILENCE_TIMEOUT_MS)
    }

    recognition.onresult = (event) => {
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
        accumulatedRef.current += (accumulatedRef.current ? ' ' : '') + finalTranscript
      }

      // Show accumulated + interim as live transcript
      const live = accumulatedRef.current + (interimTranscript ? ' ' + interimTranscript : '')
      setTranscript(live.trim())

      // Reset silence timer — user is still speaking
      resetSilenceTimer()
    }

    recognition.onerror = (event) => {
      // 'no-speech' and 'aborted' are normal in continuous mode — don't kill the session
      if (event.error === 'no-speech' || event.error === 'aborted') return
      // Fatal errors (not-allowed, service-not-allowed, network) — stop for real
      intentionalStopRef.current = true
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      setIsListening(false)
      setTranscript('')
      accumulatedRef.current = ''
    }

    recognition.onend = () => {
      // Chrome fires onend even in continuous mode (audio session interrupts,
      // noise suppression, periodic resets). Auto-restart if we didn't explicitly stop.
      if (!intentionalStopRef.current && isListeningRef.current) {
        try {
          recognition.start()
          return  // Successfully restarted — keep listening
        } catch (e) {
          // Can't restart (e.g., permission revoked) — fall through to cleanup
        }
      }

      // Intentionally stopped or can't restart — clean up
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      const text = accumulatedRef.current.trim()
      if (text && isListeningRef.current) {
        onTranscript(text)
      }
      accumulatedRef.current = ''
      setTranscript('')
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)

    // No initial silence timer — wait for the user to start speaking.
    // The timer only starts after the first onresult event (line in onresult).
    // The mic stays open until the user speaks and then pauses, or clicks stop.
  }, [speechAvailable, onTranscript])

  const stopListening = useCallback(() => {
    intentionalStopRef.current = true
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
    if (recognitionRef.current) {
      // Submit any accumulated text before stopping
      const text = accumulatedRef.current.trim()
      if (text) {
        onTranscript(text)
      }
      accumulatedRef.current = ''
      recognitionRef.current.stop()
      recognitionRef.current = null
      setIsListening(false)
      setTranscript('')
    }
  }, [onTranscript])

  // ---- TTS: Audio Playback ----

  const playNextChunk = useCallback(async () => {
    if (audioQueueRef.current.length === 0) {
      // If the SSE stream is still sending, wait longer for more chunks.
      // On slow connections (hotspot), TTS API calls can take 2-3s each,
      // so we need a generous window to avoid premature silence.
      const maxRetries = streamDoneRef.current ? 2 : 20
      for (let i = 0; i < maxRetries; i++) {
        await new Promise(r => setTimeout(r, 500))
        if (audioQueueRef.current.length > 0) break
        if (streamDoneRef.current) break
      }
      if (audioQueueRef.current.length === 0) {
        isPlayingRef.current = false
        setIsSpeaking(false)
        return
      }
    }

    isPlayingRef.current = true
    setIsSpeaking(true)

    const ctx = getAudioContext()
    const base64 = audioQueueRef.current.shift()

    try {
      const binaryStr = atob(base64)
      const bytes = new Uint8Array(binaryStr.length)
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i)
      }

      const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0))
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)
      sourceNodeRef.current = source

      source.onended = () => {
        sourceNodeRef.current = null
        playNextChunk()
      }

      source.start()
    } catch (err) {
      // Skip bad chunk, continue with next
      playNextChunk()
    }
  }, [getAudioContext])

  const markStreamDone = useCallback(() => {
    streamDoneRef.current = true
  }, [])

  // Reset buffering state for clean playback after a pause (e.g. tool execution gap)
  const prepareForNewSegment = useCallback(() => {
    bufferingRef.current = true
    if (bufferTimerRef.current) {
      clearTimeout(bufferTimerRef.current)
      bufferTimerRef.current = null
    }
  }, [])

  const enqueueAudioChunk = useCallback((base64Mp3) => {
    streamDoneRef.current = false  // Stream is actively sending chunks
    audioQueueRef.current.push(base64Mp3)

    // Pre-buffer: wait for enough chunks or a time limit before starting playback
    // This prevents gaps caused by slow chunk delivery
    if (bufferingRef.current) {
      if (audioQueueRef.current.length >= PRE_BUFFER_CHUNKS) {
        // Enough chunks buffered — start playing
        bufferingRef.current = false
        if (bufferTimerRef.current) clearTimeout(bufferTimerRef.current)
        if (!isPlayingRef.current) playNextChunk()
      } else if (!bufferTimerRef.current) {
        // Start a timeout so we don't wait forever if chunks are slow
        bufferTimerRef.current = setTimeout(() => {
          bufferTimerRef.current = null
          bufferingRef.current = false
          if (!isPlayingRef.current && audioQueueRef.current.length > 0) {
            playNextChunk()
          }
        }, PRE_BUFFER_MS)
      }
      return
    }

    if (!isPlayingRef.current) {
      playNextChunk()
    }
  }, [playNextChunk])

  const stopSpeaking = useCallback(() => {
    audioQueueRef.current = []
    bufferingRef.current = true
    if (bufferTimerRef.current) {
      clearTimeout(bufferTimerRef.current)
      bufferTimerRef.current = null
    }
    if (sourceNodeRef.current) {
      try { sourceNodeRef.current.stop() } catch (e) { /* already stopped */ }
      sourceNodeRef.current = null
    }
    isPlayingRef.current = false
    setIsSpeaking(false)
  }, [])

  const waitForPlaybackDone = useCallback(() => {
    // Returns a promise that resolves when audio playback finishes.
    // Polls isPlayingRef every 200ms, max 15 seconds.
    return new Promise(resolve => {
      if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
        resolve()
        return
      }
      let checks = 0
      const interval = setInterval(() => {
        checks++
        if ((!isPlayingRef.current && audioQueueRef.current.length === 0) || checks > 75) {
          clearInterval(interval)
          resolve()
        }
      }, 200)
    })
  }, [])

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening()
    } else {
      stopSpeaking()
      startListening()
    }
  }, [isListening, startListening, stopListening, stopSpeaking])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) recognitionRef.current.stop()
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      audioQueueRef.current = []
      if (bufferTimerRef.current) clearTimeout(bufferTimerRef.current)
      if (sourceNodeRef.current) {
        try { sourceNodeRef.current.stop() } catch (e) { /* */ }
      }
      if (audioContextRef.current) {
        audioContextRef.current.close()
      }
    }
  }, [])

  return {
    isListening,
    isSpeaking,
    transcript,
    speechAvailable,
    toggleListening,
    startListening,
    stopListening,
    stopSpeaking,
    enqueueAudioChunk,
    markStreamDone,
    waitForPlaybackDone,
    prepareForNewSegment,
  }
}
