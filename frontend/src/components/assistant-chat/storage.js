/*
 * localStorage persistence helpers for AssistantChat, relocated verbatim
 * from AssistantChat.jsx (CQ wave-3 split). The storage keys are part of
 * the persisted contract (the XSS contract test seeds messages through
 * STORAGE_KEY_MESSAGES) — do not rename.
 */
export const STORAGE_KEY_MESSAGES = 'graider_assistant_messages'
export const STORAGE_KEY_SESSION = 'graider_assistant_session'

export function loadStoredMessages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_MESSAGES)
    if (stored) return JSON.parse(stored)
  } catch (e) { /* ignore parse errors */ }
  return []
}

// Strip internal properties before saving (relocated verbatim from the
// persist-messages effect in the component)
export function stripMessagesForStorage(messages) {
  return messages.map(m => ({
    role: m.role,
    content: m.content,
    toolCalls: m.toolCalls,
    isError: m.isError,
    downloadUrl: m.downloadUrl,
    downloadFilename: m.downloadFilename,
    downloadUrls: m.downloadUrls,
    pendingSend: m.pendingSend,
    sendConfirmed: m.sendConfirmed,
    cost: m.cost,
  }))
}

export function loadStoredSession() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_SESSION)
    if (stored) return stored
  } catch (e) { /* ignore */ }
  return crypto.randomUUID()
}
