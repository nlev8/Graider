import { useState, useRef, useEffect } from 'react'
import Icon from './Icon'
import { getAuthHeaders } from '../services/api'

const API_BASE = ''

const SUGGESTED_PROMPTS = [
  { text: "What caused the low grades on the last assignment?", icon: "Search" },
  { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
  { text: "Which students need attention?", icon: "AlertTriangle" },
  { text: "Compare my class periods on the last assignment", icon: "BarChart3" },
]

const MORE_PROMPTS = [
  "What's the class average?",
  "How is [student name] doing?",
  "Show students below 60 on Cornell Notes",
  "How much did incomplete sections affect scores?",
  "What were the common feedback themes?",
  "Show assignment statistics",
  "What are students' biggest strengths?",
  "Create a Focus assignment called Quiz 3 worth 100 points",
  "Create a Cornell Notes worksheet about the American Revolution",
]

const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.docx'

function renderMarkdown(text) {
  if (!text) return ''
  let html = text
  // Markdown links [text](url) -> clickable links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, linkText, url) {
    // Download worksheet links get a special style
    if (url.indexOf('/api/download-worksheet/') !== -1) {
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

export default function AssistantChat({ addToast }) {
  const [messages, setMessages] = useState(loadStoredMessages)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId] = useState(loadStoredSession)
  const [showMorePrompts, setShowMorePrompts] = useState(false)
  const [attachedFile, setAttachedFile] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

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
    const file = e.target.files[0]
    if (!file) return
    // 20MB limit
    if (file.size > 20 * 1024 * 1024) {
      if (addToast) addToast('File too large. Maximum size is 20MB.', 'error')
      return
    }
    setAttachedFile(file)
    // Reset the input so the same file can be re-selected
    e.target.value = ''
  }

  function removeAttachedFile() {
    setAttachedFile(null)
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

  async function sendMessage(text) {
    const content = text || input.trim()
    if ((!content && !attachedFile) || isStreaming) return

    const messageText = content || 'Please analyze this file.'
    const currentFile = attachedFile

    setInput('')
    setAttachedFile(null)

    // Build user message display (show filename if attached)
    const displayContent = currentFile
      ? messageText + '\n[Attached: ' + currentFile.name + ']'
      : messageText
    const userMsg = { role: 'user', content: displayContent }
    setMessages(prev => [...prev, userMsg])
    setIsStreaming(true)

    // Add placeholder assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    try {
      // Convert file to base64 if attached
      let files = []
      if (currentFile) {
        const fileData = await fileToBase64(currentFile)
        files = [fileData]
      }

      const authHeaders = await getAuthHeaders()
      const response = await fetch(API_BASE + '/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({
          messages: [{ role: 'user', content: messageText }],
          session_id: sessionId,
          files: files,
        }),
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
                  // Insert paragraph break once when new text arrives after tool calls completed
                  let separator = ''
                  if (last.content && !last._postToolBreak
                      && last.toolCalls && last.toolCalls.length > 0
                      && last.toolCalls.every(tc => tc.status === 'done')) {
                    separator = '\n\n'
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
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  updated[updated.length - 1] = {
                    ...last,
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
                  // Capture download URL from worksheet generation
                  const newState = { ...last, toolCalls: tools }
                  if (event.download_url) {
                    newState.downloadUrl = event.download_url
                    newState.downloadFilename = event.download_filename || 'worksheet.docx'
                  }
                  updated[updated.length - 1] = newState
                }
                return updated
              })
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
    } finally {
      setIsStreaming(false)
    }
  }

  async function clearConversation() {
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
    setAttachedFile(null)
    try {
      localStorage.removeItem(STORAGE_KEY_MESSAGES)
      localStorage.removeItem(STORAGE_KEY_SESSION)
    } catch (e) { /* ignore */ }
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
  }

  const hasMessages = messages.length > 0
  const canSend = !isStreaming && (input.trim() || attachedFile)

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
        {hasMessages && (
          <button
            onClick={clearConversation}
            className="btn btn-secondary"
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
          >
            <Icon name="Trash2" size={14} />
            Clear
          </button>
        )}
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
                I can look up grades, show analytics, compare assignments, create worksheets from readings, and help with Focus gradebook.
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
                        ? (toolNameMap[tc.tool] || tc.tool).replace(/ing /, 'ed ').replace(/Querying/, 'Queried').replace(/Loading/, 'Loaded').replace(/Analyzing/, 'Analyzed').replace(/Getting/, 'Got').replace(/Listing/, 'Listed').replace(/Creating/, 'Created').replace(/Exporting/, 'Exported').replace(/Generating/, 'Generated')
                        : (toolNameMap[tc.tool] || tc.tool) + '...'}
                    </span>
                  ))}
                </div>
              )}
              {/* Download button for generated worksheets */}
              {msg.downloadUrl && (
                <div style={{ margin: '8px 0' }}>
                  <a
                    href={msg.downloadUrl}
                    download={msg.downloadFilename || 'worksheet.docx'}
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
                    Download {msg.downloadFilename || 'Worksheet'}
                  </a>
                </div>
              )}
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
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* File preview chip */}
      {attachedFile && (
        <div style={{
          padding: '6px 20px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span style={{
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
            {attachedFile.name}
            <button
              onClick={removeAttachedFile}
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
        </div>
      )}

      {/* Input Area */}
      <div style={{
        padding: '16px 20px',
        borderTop: attachedFile ? 'none' : '1px solid var(--glass-border)',
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
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={attachedFile ? 'Describe what you want (e.g., "Create a worksheet from this reading")...' : 'Ask about grades, students, or assignments...'}
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
          onClick={() => sendMessage()}
          disabled={!canSend}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            background: !canSend
              ? 'var(--glass-bg)'
              : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            border: 'none',
            color: '#fff',
            cursor: !canSend ? 'default' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: !canSend ? 0.5 : 1,
            transition: 'all 0.2s',
            flexShrink: 0,
          }}
        >
          <Icon name={isStreaming ? 'Loader2' : 'Send'} size={18} className={isStreaming ? 'spin' : ''} />
        </button>
      </div>
    </div>
  )
}
