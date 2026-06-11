import Icon from '../Icon'

/*
 * Attached-file preview chips, relocated verbatim from AssistantChat.jsx
 * (CQ wave-3 split). The parent's inline `{attachedFiles.length > 0 && ...}`
 * guard became the early-return-null below (house precedent).
 */
export default function AttachmentChips({ attachedFiles, removeAttachedFile }) {
  if (attachedFiles.length === 0) return null
  return (
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
  )
}
