import Icon from '../Icon'
import { getAuthHeaders } from '../../services/api'
import { renderMarkdown } from './markdown'
import { toolNameMap } from './toolNames'

/*
 * One chat message row (avatar + bubble + tool chips + download buttons +
 * send-confirm + typing/speaking/cost indicators), relocated verbatim from
 * the messages.map body in AssistantChat.jsx (CQ wave-3 split). The map's
 * key={idx} stays at the call site; `messages` is passed whole so the
 * `messages.length - 1` last-message checks stay byte-identical.
 */
export default function MessageBubble({ msg, idx, messages, isStreaming, voice, setMessages, addToast }) {
  return (
    <div style={{
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
        {/* Send button for email/SMS previews */}
        {msg.pendingSend && !msg.sendConfirmed && (
          <div style={{ margin: '8px 0' }}>
            <button
              onClick={async () => {
                try {
                  const authHeaders = await getAuthHeaders()
                  const resp = await fetch('/api/confirm-send', {
                    method: 'POST',
                    headers: { ...authHeaders, 'Content-Type': 'application/json' },
                    body: JSON.stringify(msg.pendingPayload || {action: 'send_focus_comms'}),
                  })
                  const data = await resp.json()
                  if (data.error) {
                    if (addToast) addToast(data.error, 'error')
                  } else {
                    if (addToast) addToast('Sending started via Focus Communications!', 'success')
                    setMessages(prev => prev.map((m, i) => i === idx ? { ...m, sendConfirmed: true } : m))
                  }
                } catch (err) {
                  if (addToast) addToast('Failed to send: ' + err.message, 'error')
                }
              }}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                padding: '10px 18px',
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#fff', border: 'none', borderRadius: '12px',
                cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '0.85' }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
            >
              <Icon name="Send" size={16} />
              Send Now
            </button>
          </div>
        )}
        {msg.sendConfirmed && (
          <div style={{ margin: '8px 0', color: '#10b981', fontWeight: 600, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Icon name="Check" size={16} /> Sending via Focus Communications
          </div>
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
  )
}
