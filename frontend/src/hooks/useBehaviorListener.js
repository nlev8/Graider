import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * Passive classroom listener using local Whisper STT via Transformers.js.
 * All audio is processed in-browser (WASM) — nothing leaves the device.
 *
 * Flow: mic → 3s chunks → Whisper Base → transcript → name detection → classification → pending event
 */

// ─── Classification patterns ───
const CORRECTION_PATTERNS = [
  /\bstop\b/i, /\bsit down\b/i, /\bfocus\b/i,
  /\bplease\s+(quiet|listen|stop)\b/i,
  /\bi need you to\b/i, /\bdon'?t\b/i, /\bpay attention\b/i,
  /\bhands to yourself\b/i, /\bthat'?s enough\b/i,
  /\bwarning\b/i, /\bin your seat\b/i, /\bturn around\b/i,
  /\bput (it |that |them )?away\b/i, /\bno (talking|phones)\b/i,
]

const PRAISE_PATTERNS = [
  /\bgood job\b/i, /\bgreat (work|job)\b/i, /\bexcellent\b/i,
  /\bthank you\b/i, /\bwell done\b/i, /\bawesome\b/i,
  /\bnice (work|job)\b/i, /\bperfect\b/i,
  /\bi'?m proud\b/i, /\bway to go\b/i, /\bkeep it up\b/i,
  /\bgood (thinking|listening|behavior)\b/i,
]

function classify(text) {
  const praiseScore = PRAISE_PATTERNS.reduce((n, p) => n + (p.test(text) ? 1 : 0), 0)
  const correctionScore = CORRECTION_PATTERNS.reduce((n, p) => n + (p.test(text) ? 1 : 0), 0)
  if (praiseScore > correctionScore) return 'praise'
  if (correctionScore > 0) return 'correction'
  return 'correction' // default to correction when unclear
}

/**
 * Build regex matchers from a roster of { name, student_id, period } objects.
 * Matches first name, last name, or "first last" as whole words.
 */
function buildNameMatchers(roster) {
  const matchers = []
  for (const student of roster) {
    const fullName = (student.name || '').trim()
    if (!fullName) continue
    const parts = fullName.split(/\s+/)
    const firstName = parts[0]
    const lastName = parts[parts.length - 1]
    // Build patterns — first name alone, last name alone, first+last
    const patterns = []
    if (firstName && firstName.length > 2) patterns.push(new RegExp('\\b' + escapeRe(firstName) + '\\b', 'i'))
    if (lastName && lastName !== firstName && lastName.length > 2) patterns.push(new RegExp('\\b' + escapeRe(lastName) + '\\b', 'i'))
    matchers.push({ student, patterns, firstName, lastName })
  }
  return matchers
}

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }


export function useBehaviorListener({ roster = [], period = '', onDetection, voiceModeActive = false }) {
  const [modelStatus, setModelStatus] = useState('idle') // idle | loading | ready | error
  const [modelProgress, setModelProgress] = useState(0)
  const [isListening, setIsListening] = useState(false)
  const [lastTranscript, setLastTranscript] = useState('')

  const pipelineRef = useRef(null)
  const streamRef = useRef(null)
  const processorRef = useRef(null)
  const audioContextRef = useRef(null)
  const chunkBufferRef = useRef([])
  const isListeningRef = useRef(false)
  const nameMatchersRef = useRef([])
  const processingRef = useRef(false)
  const intervalRef = useRef(null)

  // Update name matchers when roster changes
  useEffect(() => {
    nameMatchersRef.current = buildNameMatchers(roster)
  }, [roster])

  // Sync ref
  useEffect(() => { isListeningRef.current = isListening }, [isListening])

  /**
   * Lazy-load Whisper Base model. ~150MB, cached in browser after first download.
   */
  const loadModel = useCallback(async () => {
    if (pipelineRef.current) { setModelStatus('ready'); return true }
    setModelStatus('loading')
    setModelProgress(0)
    try {
      const { pipeline } = await import('@huggingface/transformers')
      const transcriber = await pipeline(
        'automatic-speech-recognition',
        'onnx-community/whisper-base',
        {
          dtype: 'q8',
          device: 'wasm',
          progress_callback: (progress) => {
            if (progress.progress != null) setModelProgress(Math.round(progress.progress))
          },
        }
      )
      pipelineRef.current = transcriber
      setModelStatus('ready')
      setModelProgress(100)
      return true
    } catch (e) {
      console.error('Whisper load failed:', e)
      setModelStatus('error')
      return false
    }
  }, [])

  /**
   * Start capturing audio and processing chunks.
   */
  const startListening = useCallback(async () => {
    if (isListeningRef.current) return
    // Ensure model is loaded
    if (!pipelineRef.current) {
      const ok = await loadModel()
      if (!ok) return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true }
      })
      streamRef.current = stream

      const ctx = new AudioContext({ sampleRate: 16000 })
      audioContextRef.current = ctx

      const source = ctx.createMediaStreamSource(stream)

      // Use ScriptProcessor for broader compatibility (AudioWorklet requires HTTPS + separate file)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      chunkBufferRef.current = []

      processor.onaudioprocess = (e) => {
        if (!isListeningRef.current) return
        const data = e.inputBuffer.getChannelData(0)
        chunkBufferRef.current.push(new Float32Array(data))
      }

      source.connect(processor)
      processor.connect(ctx.destination)

      setIsListening(true)

      // Process every 3 seconds
      intervalRef.current = setInterval(() => processChunk(), 3000)

    } catch (e) {
      console.error('Mic access failed:', e)
      setModelStatus('error')
    }
  }, [loadModel])

  /**
   * Process accumulated audio buffer through Whisper.
   */
  const processChunk = useCallback(async () => {
    if (processingRef.current || !pipelineRef.current) return
    const chunks = chunkBufferRef.current
    chunkBufferRef.current = []
    if (chunks.length === 0) return

    // Concatenate chunks into a single Float32Array
    const totalLength = chunks.reduce((sum, c) => sum + c.length, 0)
    const audio = new Float32Array(totalLength)
    let offset = 0
    for (const c of chunks) {
      audio.set(c, offset)
      offset += c.length
    }

    // Skip if mostly silence (RMS < threshold)
    let sumSq = 0
    for (let i = 0; i < audio.length; i++) sumSq += audio[i] * audio[i]
    const rms = Math.sqrt(sumSq / audio.length)
    if (rms < 0.01) return

    processingRef.current = true
    try {
      const result = await pipelineRef.current(audio, {
        language: 'en',
        task: 'transcribe',
        chunk_length_s: 5,
      })
      const text = (result.text || '').trim()
      if (!text || text.length < 3) return

      setLastTranscript(text)

      // Don't detect names while voice mode is active (avoid false positives)
      if (voiceModeActive) return

      // Check for student names in transcript
      detectNames(text)
    } catch (e) {
      console.error('Transcription error:', e)
    } finally {
      processingRef.current = false
    }
  }, [voiceModeActive])

  /**
   * Find student names in transcript text and dispatch detection events.
   */
  const detectNames = useCallback((text) => {
    const detected = new Set()
    for (const { student, patterns, firstName } of nameMatchersRef.current) {
      // Skip very common first names that cause false positives if alone
      // Only match if we haven't already found this student
      const key = student.student_id || student.name
      if (detected.has(key)) continue

      for (const pattern of patterns) {
        if (pattern.test(text)) {
          detected.add(key)
          const type = classify(text)
          if (onDetection) {
            onDetection({
              student_name: student.name,
              student_id: student.student_id || student.name.toLowerCase().replace(/\s+/g, '_'),
              type,
              transcript: text,
              note: '',
              timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
              period: period,
            })
          }
          break
        }
      }
    }
  }, [onDetection, period])

  /**
   * Stop listening and release resources.
   */
  const stopListening = useCallback(() => {
    setIsListening(false)
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null }
    if (audioContextRef.current) { audioContextRef.current.close().catch(() => {}); audioContextRef.current = null }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    chunkBufferRef.current = []
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (processorRef.current) processorRef.current.disconnect()
      if (audioContextRef.current) audioContextRef.current.close().catch(() => {})
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
    }
  }, [])

  return {
    modelStatus,
    modelProgress,
    isListening,
    lastTranscript,
    loadModel,
    startListening,
    stopListening,
  }
}
