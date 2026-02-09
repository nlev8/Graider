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
]

function renderMarkdown(text) {
  if (!text) return ''
  let html = text
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

export default function AssistantChat({ addToast }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())
  const [showMorePrompts, setShowMorePrompts] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  async function sendMessage(text) {
    const content = text || input.trim()
    if (!content || isStreaming) return

    setInput('')
    const userMsg = { role: 'user', content }
    setMessages(prev => [...prev, userMsg])
    setIsStreaming(true)

    // Add placeholder assistant message
    const assistantIdx = messages.length + 1
    setMessages(prev => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    try {
      const authHeaders = await getAuthHeaders()
      const response = await fetch(API_BASE + '/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({
          messages: [{ role: 'user', content }],
          session_id: sessionId,
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
                  updated[updated.length - 1] = { ...last, toolCalls: tools }
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
  }

  const hasMessages = messages.length > 0

  return (
    <div className="fade-in" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      maxHeight: 'calc(100vh - 120px)',
    }}>
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
                I can look up grades, show analytics, compare assignments, and help with Focus gradebook.
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
                        ? (toolNameMap[tc.tool] || tc.tool).replace(/ing /, 'ed ').replace(/Querying/, 'Queried').replace(/Loading/, 'Loaded').replace(/Analyzing/, 'Analyzed').replace(/Getting/, 'Got').replace(/Listing/, 'Listed').replace(/Creating/, 'Created').replace(/Exporting/, 'Exported')
                        : (toolNameMap[tc.tool] || tc.tool) + '...'}
                    </span>
                  ))}
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

      {/* Input Area */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--glass-border)',
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about grades, students, or assignments..."
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
          disabled={isStreaming || !input.trim()}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            background: isStreaming || !input.trim()
              ? 'var(--glass-bg)'
              : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            border: 'none',
            color: '#fff',
            cursor: isStreaming || !input.trim() ? 'default' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: isStreaming || !input.trim() ? 0.5 : 1,
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
