import { getAuthHeaders } from '../../services/api'

/*
 * Small fetch helpers for AssistantChat, relocated verbatim from
 * AssistantChat.jsx (CQ wave-3 split) and parameterized over the values
 * they closed over in the component (sessionId). Error-handling semantics
 * are unchanged: best-effort calls swallow errors exactly as the inline
 * originals did.
 */
export const API_BASE = ''

export async function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      const base64 = result.split(',')[1]
      resolve({
        filename: file.name,
        media_type: file.type || 'application/octet-stream',
        data: base64
      })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// Tell the backend to stop sending text to ElevenLabs (saves ElevenLabs characters/cost)
export async function muteTTSRequest(sessionId) {
  try {
    const authHeaders = await getAuthHeaders()
    fetch(API_BASE + '/api/assistant/mute-tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ session_id: sessionId }),
    })
  } catch (e) { /* best-effort */ }
}

// Cancel backend tool execution loop + mute TTS in one call (fire-and-forget,
// exactly as the inline original in stopStreaming did)
export function cancelAssistantRun(sessionId) {
  getAuthHeaders().then(authHeaders => {
    fetch(API_BASE + '/api/assistant/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ session_id: sessionId }),
    })
  }).catch(() => {})
}

// Clear all saved assistant memories (confirm prompt + toasts included —
// relocated verbatim from the component's clearMemory handler)
export async function clearAssistantMemory(addToast) {
  if (!window.confirm('Clear all saved memories? The assistant will no longer remember facts from previous conversations.')) return
  try {
    const authHeaders = await getAuthHeaders()
    await fetch(API_BASE + '/api/assistant/memory', {
      method: 'DELETE',
      headers: authHeaders,
    })
    if (addToast) addToast('Assistant memory cleared', 'success')
  } catch (e) {
    if (addToast) addToast('Failed to clear memory', 'error')
  }
}

// Clear the server-side conversation for this session (errors ignored,
// exactly as the inline original in clearConversation did)
export async function clearAssistantSession(sessionId) {
  try {
    const authHeaders = await getAuthHeaders()
    await fetch(API_BASE + '/api/assistant/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ session_id: sessionId }),
    })
  } catch (e) {
    // Ignore clear errors
  }
}
