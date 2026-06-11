import { getAuthHeaders } from '../../services/api'
import { API_BASE } from './api'

/*
 * SSE streaming for the assistant chat, relocated verbatim from the body
 * of sendMessage in AssistantChat.jsx (CQ wave-3 split).
 *
 * Behavior-preserving notes:
 *   - voice_mode is read from voiceModeRef.current at body-build time
 *     (after the getAuthHeaders await), exactly as the inline original.
 *   - `await onEvent(event)` sits INSIDE the same try/catch that wraps
 *     JSON.parse: in the original, an error thrown while processing an
 *     event (e.g. voice.waitForPlaybackDone rejecting) was swallowed by
 *     the parse catch and the line skipped. That semantics is preserved.
 */
export async function streamAssistantChat({ messageText, sessionId, files, voiceModeRef, signal, onEvent }) {
  const authHeaders = await getAuthHeaders()
  const response = await fetch(API_BASE + '/api/assistant/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({
      messages: [{ role: 'user', content: messageText }],
      session_id: sessionId,
      files: files,
      voice_mode: voiceModeRef.current,
    }),
    signal,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Request failed' }))
    throw new Error(err.error || 'Request failed')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const jsonStr = line.slice(6).trim()
      if (!jsonStr) continue

      try {
        const event = JSON.parse(jsonStr)
        await onEvent(event)
      } catch (parseErr) {
        // Skip malformed JSON
      }
    }
  }
}

/*
 * Per-event state updates, relocated verbatim from the event if/else chain
 * inside sendMessage. ctx carries exactly the closures the original code
 * captured from the component: setMessages, setSessionCost, addToast,
 * voice, voiceModeRef.
 */
export async function processAssistantEvent(event, ctx) {
  const { setMessages, setSessionCost, addToast, voice, voiceModeRef } = ctx

  if (event.type === 'text_delta') {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        // Insert paragraph break when new text arrives after tool calls completed,
        // but only if the existing content ends at a sentence boundary (not mid-sentence)
        let separator = ''
        if (last.content && !last._postToolBreak
            && last.toolCalls && last.toolCalls.length > 0
            && last.toolCalls.every(tc => tc.status === 'done')) {
          const trimmed = last.content.trimEnd()
          const lastChar = trimmed.charAt(trimmed.length - 1)
          separator = /[.!?:)\]\n]/.test(lastChar) ? '\n\n' : ' '
        }
        updated[updated.length - 1] = {
          ...last,
          content: last.content + separator + event.content,
          _postToolBreak: separator ? true : last._postToolBreak
        }
      }
      return updated
    })
  } else if (event.type === 'tool_start') {
    // In voice mode, wait for audio to finish playing before
    // showing the tool spinner — let the AI finish its sentence
    if (voiceModeRef.current) {
      await voice.waitForPlaybackDone()
      voice.prepareForNewSegment()  // Reset buffering for clean post-tool audio
    }
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        updated[updated.length - 1] = {
          ...last,
          _postToolBreak: false,  // Reset so next text batch gets a paragraph break
          toolCalls: [...(last.toolCalls || []), {
            id: event.id,
            tool: event.tool,
            status: 'running'
          }]
        }
      }
      return updated
    })
  } else if (event.type === 'tool_result') {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        const tools = (last.toolCalls || []).map(tc =>
          tc.id === event.id ? { ...tc, status: 'done', preview: event.result_preview } : tc
        )
        // Capture download URL(s) from any file-generating tool
        const newState = { ...last, toolCalls: tools }
        if (event.download_url) {
          newState.downloadUrl = event.download_url
          newState.downloadFilename = event.download_filename || 'file'
        }
        if (event.download_urls) {
          newState.downloadUrls = [...(last.downloadUrls || []), ...event.download_urls]
        }
        if (event.pending_send) {
          newState.pendingSend = true
          if (event.pending_payload) {
            newState.pendingPayload = event.pending_payload
          }
        }
        updated[updated.length - 1] = newState
      }
      return updated
    })
  } else if (event.type === 'audio_chunk') {
    if (voiceModeRef.current && event.audio) {
      voice.enqueueAudioChunk(event.audio)
    }
  } else if (event.type === 'cost_warning') {
    if (addToast) addToast(
      'High token usage: ~$' + event.estimated_cost.toFixed(4) + ' after ' + event.rounds_used + ' tool rounds. Query stopped to save cost.',
      'warning',
      8000
    )
  } else if (event.type === 'cost') {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        updated[updated.length - 1] = { ...last, cost: event }
      }
      return updated
    })
    setSessionCost(prev => prev + (event.total_cost || 0))
    if (event.high_cost && addToast) {
      addToast('Expensive query: $' + event.total_cost.toFixed(4) + '. Try a more specific question to reduce cost.', 'warning', 8000)
    }
  } else if (event.type === 'error') {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.role === 'assistant') {
        updated[updated.length - 1] = {
          ...last,
          content: last.content + '\n\n' + event.content,
          isError: true
        }
      }
      return updated
    })
  }
}
