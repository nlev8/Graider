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
  const audioContextRef = useRef(null)
  const audioQueueRef = useRef([])
  const isPlayingRef = useRef(false)
  const sourceNodeRef = useRef(null)

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

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = 'en-US'

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

      setTranscript(interimTranscript || finalTranscript)

      if (finalTranscript) {
        onTranscript(finalTranscript.trim())
        setTranscript('')
        setIsListening(false)
      }
    }

    recognition.onerror = () => {
      setIsListening(false)
      setTranscript('')
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [speechAvailable, onTranscript])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
      setIsListening(false)
      setTranscript('')
    }
  }, [])

  // ---- TTS: Audio Playback ----

  const playNextChunk = useCallback(async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false
      setIsSpeaking(false)
      return
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

  const enqueueAudioChunk = useCallback((base64Mp3) => {
    audioQueueRef.current.push(base64Mp3)
    if (!isPlayingRef.current) {
      playNextChunk()
    }
  }, [playNextChunk])

  const stopSpeaking = useCallback(() => {
    audioQueueRef.current = []
    if (sourceNodeRef.current) {
      try { sourceNodeRef.current.stop() } catch (e) { /* already stopped */ }
      sourceNodeRef.current = null
    }
    isPlayingRef.current = false
    setIsSpeaking(false)
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
      audioQueueRef.current = []
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
  }
}
