import Icon from '../Icon'

/*
 * Empty-conversation hero + suggested-prompt chips, relocated verbatim
 * from AssistantChat.jsx (CQ wave-3 split). The parent's inline
 * `{!hasMessages && (...)}` guard became the early-return-null below
 * (house precedent); prop names match the original local identifiers.
 */
export default function EmptyState({ hasMessages, SUGGESTED_PROMPTS, MORE_PROMPTS, showMorePrompts, setShowMorePrompts, sendMessage }) {
  if (hasMessages) return null
  return (
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
  )
}
