import { useState, useRef, useEffect, useCallback } from 'react'
import { getAuthHeaders } from '../../services/api'
import { useVoice } from '../../hooks/useVoice'
import { API_BASE, fileToBase64, muteTTSRequest, cancelAssistantRun, clearAssistantSession, clearAssistantMemory } from './api'
import { streamAssistantChat, processAssistantEvent } from './streaming'
import { STORAGE_KEY_MESSAGES, STORAGE_KEY_SESSION, loadStoredMessages, loadStoredSession, stripMessagesForStorage } from './storage'

/*
 * useAssistantChat — owns ALL AssistantChat state, refs, effects, and
 * handlers, relocated verbatim from AssistantChat.jsx (CQ wave-3 split;
 * mirrors the wave-2 useIndividualUpload precedent for state/effect
 * clusters).
 *
 * Behavior-preserving notes:
 *   - Called unconditionally from the always-mounted AssistantChat shell,
 *     so every effect keeps the exact mount/unmount lifecycle and a
 *     byte-identical dependency array it had inline.
 *   - The streaming fetch + SSE read loop lives in sendMessage (via
 *     streamAssistantChat) and the abort/scroll refs stay owned here —
 *     the timing-sensitive chat lifecycle never moves into a child that
 *     could unmount.
 *   - Handlers are intentionally NOT memoized (no useCallback) — same as
 *     the pre-split plain declarations recreated each render.
 */
export default function useAssistantChat({ addToast }) {
  const [messages, setMessages] = useState(loadStoredMessages)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId] = useState(loadStoredSession)
  const [showMorePrompts, setShowMorePrompts] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState([])
  const [voiceMode, setVoiceMode] = useState(false)
  const [voiceAvailable, setVoiceAvailable] = useState(false)
  const [sessionCost, setSessionCost] = useState(0)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const voiceModeRef = useRef(false)
  const abortControllerRef = useRef(null)

  // Keep ref in sync with state for use in SSE callback
  useEffect(() => { voiceModeRef.current = voiceMode }, [voiceMode])

  // Voice hook — sendMessage defined below, so we use a ref callback
  const sendMessageRef = useRef(null)
  const onVoiceTranscript = useCallback((text) => {
    if (sendMessageRef.current) sendMessageRef.current(text)
  }, [])

  const voice = useVoice({ onTranscript: onVoiceTranscript })

  // Check if voice is configured on backend
  useEffect(() => {
    async function checkVoice() {
      try {
        const authHeaders = await getAuthHeaders()
        const resp = await fetch(API_BASE + '/api/assistant/voice-config', {
          headers: authHeaders
        })
        const data = await resp.json()
        setVoiceAvailable(data.enabled && voice.speechAvailable)
      } catch (e) {
        setVoiceAvailable(false)
      }
    }
    checkVoice()
  }, [voice.speechAvailable])

  // Persist messages and session to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(stripMessagesForStorage(messages)))
    } catch (e) { /* storage full or unavailable */ }
  }, [messages])

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_SESSION, sessionId)
    } catch (e) { /* ignore */ }
  }, [sessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleFileSelect(e) {
    const selected = Array.from(e.target.files)
    if (!selected.length) return
    const tooLarge = selected.filter(f => f.size > 20 * 1024 * 1024)
    if (tooLarge.length) {
      if (addToast) addToast('File too large: ' + tooLarge.map(f => f.name).join(', ') + '. Maximum size is 20MB per file.', 'error')
    }
    const valid = selected.filter(f => f.size <= 20 * 1024 * 1024)
    if (valid.length) {
      setAttachedFiles(prev => {
        const combined = [...prev, ...valid]
        if (combined.length > 10) {
          if (addToast) addToast('Maximum 10 files allowed. Only the first 10 were kept.', 'warning')
          return combined.slice(0, 10)
        }
        return combined
      })
    }
    // Reset the input so the same file can be re-selected
    e.target.value = ''
  }

  function removeAttachedFile(index) {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Tell the backend to stop sending text to ElevenLabs (saves ElevenLabs characters/cost)
  function muteTTS() {
    muteTTSRequest(sessionId)
  }

  async function sendMessage(text) {
    const content = text || input.trim()
    if ((!content && attachedFiles.length === 0) || isStreaming) return

    // Barge-in: stop audio and mute TTS on backend
    if (voice.isSpeaking) {
      voice.stopSpeaking()
      muteTTS()
    }

    const messageText = content || 'Please analyze ' + (attachedFiles.length === 1 ? 'this file.' : 'these files.')
    const currentFiles = [...attachedFiles]

    setInput('')
    setAttachedFiles([])

    // Build user message display (show filenames if attached)
    const displayContent = currentFiles.length > 0
      ? messageText + '\n[Attached: ' + currentFiles.map(f => f.name).join(', ') + ']'
      : messageText
    const userMsg = { role: 'user', content: displayContent }
    setMessages(prev => [...prev, userMsg])
    setIsStreaming(true)

    // Add placeholder assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    try {
      // Convert files to base64 if attached
      let files = []
      if (currentFiles.length > 0) {
        files = await Promise.all(currentFiles.map(f => fileToBase64(f)))
      }

      const controller = new AbortController()
      abortControllerRef.current = controller

      await streamAssistantChat({
        messageText,
        sessionId,
        files,
        voiceModeRef,
        signal: controller.signal,
        onEvent: (event) => processAssistantEvent(event, {
          setMessages, setSessionCost, addToast, voice, voiceModeRef,
        }),
      })
    } catch (err) {
      // AbortError means user clicked stop — not an error
      if (err.name === 'AbortError') {
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + (last.content ? '\n\n*[Stopped]*' : '*[Stopped]*'),
            }
          }
          return updated
        })
      } else {
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: 'Sorry, something went wrong: ' + err.message,
              isError: true
            }
          }
          return updated
        })
        if (addToast) addToast('Assistant error: ' + err.message, 'error')
      }
    } finally {
      abortControllerRef.current = null
      setIsStreaming(false)
      // Signal the voice player that no more audio chunks will arrive
      voice.markStreamDone()
    }
  }

  // Wire up ref so voice hook can call sendMessage
  sendMessageRef.current = sendMessage

  // Listen for behavior email requests from BehaviorPanel
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.message && sendMessageRef.current) {
        sendMessageRef.current(e.detail.message)
      }
    }
    window.addEventListener('behavior-email-request', handler)
    return () => window.removeEventListener('behavior-email-request', handler)
  }, [])

  function stopStreaming() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    // Stop TTS playback and mute backend
    if (voice.isSpeaking) {
      voice.stopSpeaking()
    }
    // Cancel backend tool execution loop + mute TTS in one call
    cancelAssistantRun(sessionId)
  }

  async function clearConversation() {
    // Stop any active stream first
    if (isStreaming) stopStreaming()

    await clearAssistantSession(sessionId)
    setMessages([])
    setAttachedFiles([])
    setSessionCost(0)
    try {
      localStorage.removeItem(STORAGE_KEY_MESSAGES)
    } catch (e) { /* ignore */ }
  }

  function clearMemory() {
    clearAssistantMemory(addToast)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return {
    messages, setMessages,
    input, setInput,
    isStreaming,
    showMorePrompts, setShowMorePrompts,
    attachedFiles,
    voiceMode, setVoiceMode,
    voiceAvailable,
    sessionCost,
    messagesEndRef, inputRef, fileInputRef,
    voice,
    handleFileSelect, removeAttachedFile,
    muteTTS, sendMessage, stopStreaming,
    clearConversation, clearMemory, handleKeyDown,
  }
}
