import Icon from '../Icon'

/*
 * Header bar (title + session cost + Clear Chat / Clear Memory buttons),
 * relocated verbatim from AssistantChat.jsx (CQ wave-3 split). Prop names
 * match the original local identifiers so the JSX is unchanged.
 */
export default function ChatHeader({ sessionCost, hasMessages, clearConversation, clearMemory }) {
  return (
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
  )
}
