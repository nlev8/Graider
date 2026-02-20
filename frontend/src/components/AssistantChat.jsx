import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import Icon from './Icon'
import { getAuthHeaders } from '../services/api'
import { useVoice } from '../hooks/useVoice'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const API_BASE = ''

const DEFAULT_SUGGESTED = [
  { text: "How is my class doing across the rubric categories?", icon: "Target" },
  { text: "What caused the low grades on the last assignment?", icon: "Search" },
  { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
  { text: "Which students need attention?", icon: "AlertTriangle" },
]

const DEFAULT_MORE = [
  "What's the class average?",
  "How is [student name] doing?",
  "Which rubric category is my class weakest in?",
  "Compare my class periods on the last assignment",
  "Show students below 60 on Cornell Notes",
  "How much did incomplete sections affect scores?",
  "What were the common feedback themes?",
  "Show assignment statistics",
  "What are students' biggest strengths?",
  "Create a Focus assignment called Quiz 3 worth 100 points",
  "Create a Cornell Notes worksheet about the American Revolution",
  "How do I set up my rubric?",
  "What export options are available?",
  "How does the grading pipeline work?",
]

const SUBJECT_SUGGESTED = {
  "Math": [
    { text: "Check if 2x+3 is equivalent to 3+2x", icon: "Calculator" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
  "Science": [
    { text: "How is my class doing across the rubric categories?", icon: "Target" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "Grade this lab data table against the answer key", icon: "Table" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
  "Geography": [
    { text: "Check if 48.85N, 2.35E is close enough to Paris", icon: "MapPin" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
}

const SUBJECT_MORE = {
  "Math": [
    "Is \\frac{1}{2} equivalent to 0.5?",
    "Grade this math answer: student wrote 3x^2+6x, correct answer is 3x(x+2)",
    "Create a worksheet about solving linear equations",
    "What are the weakest math standards for my class?",
  ],
  "Science": [
    "Compare student lab data against the expected values with 5% tolerance",
    "Create a worksheet about the scientific method",
    "What are the weakest science standards for my class?",
    "Which students struggled most with data analysis?",
  ],
  "Geography": [
    "Is 'Britain' an acceptable answer for 'United Kingdom'?",
    "How far off is 40.7N, 74.0W from New York City?",
    "Create a worksheet about world capitals",
    "What are the weakest geography standards for my class?",
  ],
  "US History": [
    "Create a Cornell Notes worksheet about the Civil War",
    "What are the weakest history standards for my class?",
    "Which students struggled most with source analysis?",
    "Create a Kahoot quiz on the American Revolution",
  ],
  "Social Studies": [
    "Create a worksheet about civic responsibility",
    "What are the weakest social studies standards for my class?",
    "Compare my class periods on the last assignment",
    "Create a Blooket set from the civics standards vocabulary",
  ],
  "ELA": [
    "Create a short-answer worksheet about theme and character development",
    "What are the weakest ELA standards for my class?",
    "Which students struggled most with written communication?",
    "What were the common feedback themes on the essay?",
  ],
  "English/ELA": [
    "Create a short-answer worksheet about theme and character development",
    "What are the weakest ELA standards for my class?",
    "Which students struggled most with written communication?",
    "What were the common feedback themes on the essay?",
  ],
}

function getSubjectPrompts(subject) {
  if (!subject) return { suggested: DEFAULT_SUGGESTED, more: DEFAULT_MORE }
  const subjectMore = SUBJECT_MORE[subject] || []
  return {
    suggested: SUBJECT_SUGGESTED[subject] || DEFAULT_SUGGESTED,
    more: [...subjectMore, ...DEFAULT_MORE],
  }
}

const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.docx'

function renderMarkdown(text) {
  if (!text) return ''
  let html = text

  // Placeholder system: protect complex HTML (KaTeX, images) from later regex passes
  var placeholders = []
  function ph(content) {
    var id = '\x00PH' + placeholders.length + '\x00'
    placeholders.push(content)
    return id
  }

  // Block math: $$...$$
  html = html.replace(/\$\$([\s\S]+?)\$\$/g, function(m, latex) {
    try {
      return ph('<div style="margin:8px 0;text-align:center">' +
        katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false }) + '</div>')
    } catch (e) {
      return ph('<code style="color:#f87171">' + latex + '</code>')
    }
  })

  // Inline math: $...$  (skip currency like $5.00)
  html = html.replace(/\$([^\$\n]+?)\$/g, function(m, latex) {
    if (/^\d/.test(latex.trim())) return m
    try {
      return ph(katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false }))
    } catch (e) {
      return ph('<code style="color:#f87171">' + latex + '</code>')
    }
  })

  // Markdown images: ![alt](url) — supports base64 data URIs and regular URLs
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(m, alt, url) {
    return ph('<img src="' + url + '" alt="' + alt +
      '" style="max-width:100%;border-radius:8px;margin:8px 0;display:block" />')
  })

  // Markdown links [text](url) -> clickable links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, linkText, url) {
    // Download worksheet links get a special style
    if (url.indexOf('/api/download-worksheet/') !== -1 || url.indexOf('/api/download-document/') !== -1) {
      return '<a href="' + url + '" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:12px;text-decoration:none;font-weight:600;font-size:0.85em;margin:4px 0" download>' + linkText + '</a>'
    }
    return '<a href="' + url + '" style="color:var(--accent-light);text-decoration:underline" target="_blank" rel="noopener">' + linkText + '</a>'
  })
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(99,102,241,0.15);padding:2px 6px;border-radius:4px;font-size:0.85em">$1</code>')
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:0.95em">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:10px 0 4px;font-size:1.05em">$1</h3>')
  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>')
  // Paragraphs (double newlines)
  html = html.replace(/\n\n/g, '<br/><br/>')
  // Single newlines
  html = html.replace(/\n/g, '<br/>')

  // Restore placeholders
  for (var i = 0; i < placeholders.length; i++) {
    html = html.split('\x00PH' + i + '\x00').join(placeholders[i])
  }
  return html
}

const STORAGE_KEY_MESSAGES = 'graider_assistant_messages'
const STORAGE_KEY_SESSION = 'graider_assistant_session'

function loadStoredMessages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_MESSAGES)
    if (stored) return JSON.parse(stored)
  } catch (e) { /* ignore parse errors */ }
  return []
}

function loadStoredSession() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_SESSION)
    if (stored) return stored
  } catch (e) { /* ignore */ }
  return crypto.randomUUID()
}

export default function AssistantChat({ addToast, subject }) {
  const { suggested: SUGGESTED_PROMPTS, more: MORE_PROMPTS } = useMemo(
    () => getSubjectPrompts(subject), [subject]
  )
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
      // Strip internal properties before saving
      const toStore = messages.map(m => ({
        role: m.role,
        content: m.content,
        toolCalls: m.toolCalls,
        isError: m.isError,
        downloadUrl: m.downloadUrl,
        downloadFilename: m.downloadFilename,
        downloadUrls: m.downloadUrls,
        cost: m.cost,
      }))
      localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(toStore))
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

  async function fileToBase64(file) {
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
  async function muteTTS() {
    try {
      const authHeaders = await getAuthHeaders()
      fetch(API_BASE + '/api/assistant/mute-tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ session_id: sessionId }),
      })
    } catch (e) { /* best-effort */ }
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
        signal: controller.signal,
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
          } catch (parseErr) {
            // Skip malformed JSON
          }
        }
      }
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
    getAuthHeaders().then(authHeaders => {
      fetch(API_BASE + '/api/assistant/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ session_id: sessionId }),
      })
    }).catch(() => {})
  }

  async function clearConversation() {
    // Stop any active stream first
    if (isStreaming) stopStreaming()

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
    setMessages([])
    setAttachedFiles([])
    setSessionCost(0)
    try {
      localStorage.removeItem(STORAGE_KEY_MESSAGES)
    } catch (e) { /* ignore */ }
  }

  async function clearMemory() {
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

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const toolNameMap = {
    query_grades: 'Querying grades',
    get_student_summary: 'Loading student summary',
    get_class_analytics: 'Analyzing class data',
    get_assignment_stats: 'Getting assignment stats',
    list_assignments: 'Listing assignments',
    analyze_grade_causes: 'Analyzing grade causes',
    get_feedback_patterns: 'Analyzing feedback patterns',
    compare_periods: 'Comparing periods',
    recommend_next_lesson: 'Analyzing for lesson recommendation',
    create_focus_assignment: 'Creating Focus assignment',
    export_grades_csv: 'Exporting CSV',
    generate_worksheet: 'Generating worksheet',
    generate_document: 'Generating document',
    generate_csv: 'Generating CSV file',
    save_document_style: 'Saving document style',
    list_document_styles: 'Checking saved styles',
    save_memory: 'Saving to memory',
    get_standards: 'Looking up standards',
    list_all_standards: 'Loading standards index',
    get_recent_lessons: 'Loading recent lessons',
    get_calendar: 'Checking calendar',
    schedule_lesson: 'Scheduling lesson',
    add_calendar_holiday: 'Adding holiday',
    list_resources: 'Loading resources',
    read_resource: 'Reading document',
  }

  const hasMessages = messages.length > 0
  const canSend = !isStreaming && (input.trim() || attachedFiles.length > 0)

  return (
    <div className="fade-in" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      maxHeight: 'calc(100vh - 120px)',
    }}>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FILE_TYPES}
        onChange={handleFileSelect}
        multiple
        style={{ display: 'none' }}
      />

      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 20px',
        borderBottom: '1px solid var(--glass-border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Icon name="Sparkles" size={22} style={{ color: 'var(--accent-primary)' }} />
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>
            Graider Assistant
          </h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {sessionCost > 0 && (
            <span style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              padding: '4px 10px',
              background: 'var(--glass-bg)',
              borderRadius: '12px',
              border: '1px solid var(--glass-border)',
            }}>
              Session: ${sessionCost.toFixed(4)}
            </span>
          )}
          {hasMessages && (
            <button
              onClick={clearConversation}
              className="btn btn-secondary"
              style={{ padding: '6px 14px', fontSize: '0.8rem' }}
              title="Clear chat window (memory is preserved)"
            >
              <Icon name="Trash2" size={14} />
              Clear Chat
            </button>
          )}
          <button
            onClick={clearMemory}
            className="btn btn-secondary"
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
            title="Clear saved facts from previous conversations"
          >
            <Icon name="BrainCircuit" size={14} />
            Clear Memory
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {!hasMessages && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            flex: 1,
            gap: '24px',
            padding: '40px 20px',
          }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Icon name="Sparkles" size={28} style={{ color: '#fff' }} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '8px' }}>
                Ask about your students
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '400px' }}>
                I can analyze rubric performance, spot trends, look up grades, compare assignments, create worksheets from readings, and help with Focus gradebook.
              </p>
            </div>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '10px',
              justifyContent: 'center',
              maxWidth: '500px',
            }}>
              {SUGGESTED_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(prompt.text)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 16px',
                    background: 'var(--glass-bg)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '20px',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'var(--glass-hover)'
                    e.currentTarget.style.borderColor = 'var(--accent-primary)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'var(--glass-bg)'
                    e.currentTarget.style.borderColor = 'var(--glass-border)'
                  }}
                >
                  <Icon name={prompt.icon} size={16} style={{ color: 'var(--accent-primary)' }} />
                  {prompt.text}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowMorePrompts(!showMorePrompts)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-light)',
                cursor: 'pointer',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                marginTop: '4px',
              }}
            >
              <Icon name={showMorePrompts ? 'ChevronUp' : 'ChevronDown'} size={14} />
              {showMorePrompts ? 'Less ideas' : 'More ideas'}
            </button>
            {showMorePrompts && (
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                justifyContent: 'center',
                maxWidth: '540px',
              }}>
                {MORE_PROMPTS.map((text, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(text)}
                    style={{
                      padding: '6px 14px',
                      background: 'var(--glass-bg)',
                      border: '1px solid var(--glass-border)',
                      borderRadius: '16px',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = 'var(--glass-hover)'
                      e.currentTarget.style.color = 'var(--text-primary)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = 'var(--glass-bg)'
                      e.currentTarget.style.color = 'var(--text-secondary)'
                    }}
                  >
                    {text}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} style={{
            display: 'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            gap: '10px',
          }}>
            {msg.role === 'assistant' && (
              <div style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                marginTop: '2px',
              }}>
                <Icon name="Sparkles" size={16} style={{ color: '#fff' }} />
              </div>
            )}
            <div style={{
              maxWidth: '75%',
              padding: '12px 16px',
              borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
              background: msg.role === 'user'
                ? 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))'
                : 'var(--glass-bg)',
              border: msg.role === 'user' ? 'none' : '1px solid var(--glass-border)',
              color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
              fontSize: '0.9rem',
              lineHeight: '1.5',
              wordBreak: 'break-word',
            }}>
              {/* Tool call indicators */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div style={{ marginBottom: msg.content ? '8px' : 0, display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {msg.toolCalls.map((tc, ti) => (
                    <span key={ti} style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '3px 10px',
                      borderRadius: '12px',
                      fontSize: '0.75rem',
                      background: tc.status === 'done'
                        ? 'rgba(74, 222, 128, 0.15)'
                        : 'rgba(99, 102, 241, 0.15)',
                      color: tc.status === 'done' ? 'var(--success)' : 'var(--accent-light)',
                    }}>
                      <Icon
                        name={tc.status === 'done' ? 'CheckCircle2' : 'Loader2'}
                        size={12}
                        className={tc.status === 'running' ? 'spin' : ''}
                      />
                      {tc.status === 'done'
                        ? (toolNameMap[tc.tool] || tc.tool).replace(/^Querying/, 'Queried').replace(/^Loading/, 'Loaded').replace(/^Analyzing/, 'Analyzed').replace(/^Getting/, 'Got').replace(/^Listing/, 'Listed').replace(/^Creating/, 'Created').replace(/^Exporting/, 'Exported').replace(/^Generating/, 'Generated').replace(/^Reading/, 'Read').replace(/^Checking/, 'Checked').replace(/^Scheduling/, 'Scheduled').replace(/^Adding/, 'Added').replace(/^Saving/, 'Saved').replace(/^Looking/, 'Looked')
                        : (toolNameMap[tc.tool] || tc.tool) + '...'}
                    </span>
                  ))}
                </div>
              )}
              {/* Download buttons for generated files (worksheets, CSV exports, etc.) */}
              {(msg.downloadUrls || (msg.downloadUrl ? [{ url: msg.downloadUrl, filename: msg.downloadFilename }] : [])).map((dl, di) => (
                <div key={di} style={{ margin: '4px 0' }}>
                  <a
                    href={dl.url}
                    download={dl.filename || 'file'}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 18px',
                      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                      color: '#fff',
                      borderRadius: '12px',
                      textDecoration: 'none',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      transition: 'opacity 0.2s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.opacity = '0.85' }}
                    onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
                  >
                    <Icon name="Download" size={16} />
                    Download {dl.filename || 'File'}
                  </a>
                </div>
              ))}
              {msg.role === 'assistant' ? (
                <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
              ) : (
                msg.content
              )}
              {msg.role === 'assistant' && !msg.content && isStreaming && idx === messages.length - 1 && (
                <span style={{ display: 'inline-flex', gap: '3px', opacity: 0.5 }}>
                  <span className="typing-dot" style={{ animationDelay: '0s' }}>.</span>
                  <span className="typing-dot" style={{ animationDelay: '0.2s' }}>.</span>
                  <span className="typing-dot" style={{ animationDelay: '0.4s' }}>.</span>
                </span>
              )}
              {voice.isSpeaking && msg.role === 'assistant' && idx === messages.length - 1 && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  marginTop: '6px',
                  fontSize: '0.75rem',
                  color: 'var(--accent-light)',
                }}>
                  <Icon name="Volume2" size={12} />
                  Speaking...
                </div>
              )}
              {msg.cost && msg.cost.total_cost > 0 && (
                <div style={{
                  marginTop: '6px',
                  fontSize: '0.7rem',
                  color: msg.cost.total_cost > 0.25 ? '#f87171' :
                         msg.cost.total_cost > 0.05 ? '#fbbf24' :
                         'var(--text-secondary)',
                  opacity: msg.cost.total_cost > 0.05 ? 0.9 : 0.6,
                  fontWeight: msg.cost.total_cost > 0.25 ? 600 : 400,
                }}>
                  ${msg.cost.total_cost.toFixed(4)}
                  {msg.cost.tts_cost > 0 ? ' (incl. voice)' : ''}
                  {msg.cost.total_cost > 0.25 ? ' — high cost' : ''}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Voice interim transcript */}
      {voice.isListening && voice.transcript && (
        <div style={{
          padding: '6px 20px',
          fontSize: '0.85rem',
          color: 'var(--accent-light)',
          fontStyle: 'italic',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <Icon name="Mic" size={14} style={{ color: '#ef4444' }} />
          {voice.transcript}
        </div>
      )}

      {/* File preview chips */}
      {attachedFiles.length > 0 && (
        <div style={{
          padding: '6px 20px 0',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '8px',
        }}>
          {attachedFiles.map((file, i) => (
            <span key={i} style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 12px',
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '12px',
              fontSize: '0.8rem',
              color: 'var(--accent-light)',
            }}>
              <Icon name="Paperclip" size={13} />
              {file.name}
              <button
                onClick={() => removeAttachedFile(i)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  padding: '0 2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Icon name="X" size={13} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input Area */}
      <div style={{
        padding: '16px 20px',
        borderTop: attachedFiles.length > 0 ? 'none' : '1px solid var(--glass-border)',
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-end',
      }}>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isStreaming}
          title="Attach file (image, PDF, or DOCX)"
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            background: 'var(--glass-bg)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-secondary)',
            cursor: isStreaming ? 'default' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: isStreaming ? 0.5 : 1,
            transition: 'all 0.2s',
            flexShrink: 0,
          }}
        >
          <Icon name="Paperclip" size={18} />
        </button>
        {/* Voice mode toggle */}
        {voiceAvailable && (
          <button
            onClick={() => {
              const next = !voiceMode
              setVoiceMode(next)
              if (!next) {
                voice.stopSpeaking()
                muteTTS()
              }
            }}
            title={voiceMode ? 'Disable voice mode' : 'Enable voice mode'}
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              background: voiceMode
                ? 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))'
                : 'var(--glass-bg)',
              border: voiceMode ? 'none' : '1px solid var(--glass-border)',
              color: voiceMode ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
              flexShrink: 0,
            }}
          >
            <Icon name={voiceMode ? 'Volume2' : 'VolumeX'} size={18} />
          </button>
        )}
        {/* Mic button (voice mode only) */}
        {voiceMode && (
          <button
            onClick={voice.toggleListening}
            disabled={isStreaming}
            title={voice.isListening ? 'Stop listening' : 'Speak to assistant'}
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              background: voice.isListening
                ? 'linear-gradient(135deg, #ef4444, #dc2626)'
                : 'var(--glass-bg)',
              border: voice.isListening ? 'none' : '1px solid var(--glass-border)',
              color: voice.isListening ? '#fff' : 'var(--text-secondary)',
              cursor: isStreaming ? 'default' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: isStreaming ? 0.5 : 1,
              transition: 'all 0.2s',
              flexShrink: 0,
              boxShadow: voice.isListening ? '0 0 0 0 rgba(239, 68, 68, 0.4)' : 'none',
              animation: voice.isListening ? 'micPulse 1.5s ease-in-out infinite' : 'none',
            }}
          >
            <Icon name={voice.isListening ? 'MicOff' : 'Mic'} size={18} />
          </button>
        )}
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={attachedFiles.length > 0 ? 'Describe what you want (e.g., "Create a worksheet from this reading")...' : 'Ask about grades, students, or assignments...'}
          disabled={isStreaming}
          rows={1}
          style={{
            flex: 1,
            padding: '12px 16px',
            background: 'var(--input-bg)',
            border: '1px solid var(--input-border)',
            borderRadius: '16px',
            color: 'var(--text-primary)',
            fontSize: '0.9rem',
            resize: 'none',
            outline: 'none',
            fontFamily: 'inherit',
            maxHeight: '120px',
            overflow: 'auto',
          }}
          onInput={e => {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
          }}
        />
        <button
          onClick={isStreaming ? stopStreaming : () => sendMessage()}
          disabled={!isStreaming && !canSend}
          title={isStreaming ? 'Stop generating' : 'Send message'}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            background: isStreaming
              ? 'linear-gradient(135deg, #ef4444, #dc2626)'
              : !canSend
                ? 'var(--glass-bg)'
                : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            border: isStreaming ? '2px solid #fca5a5' : 'none',
            color: '#fff',
            cursor: (!isStreaming && !canSend) ? 'default' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: (!isStreaming && !canSend) ? 0.5 : 1,
            transition: 'all 0.2s',
            flexShrink: 0,
            boxShadow: isStreaming ? '0 0 12px rgba(239, 68, 68, 0.5)' : 'none',
          }}
        >
          {isStreaming ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
              <rect x="0" y="0" width="14" height="14" rx="2" />
            </svg>
          ) : (
            <Icon name="Send" size={18} />
          )}
        </button>
      </div>
    </div>
  )
}
