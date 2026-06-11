import Icon from '../Icon'

/*
 * Input row (attach button, voice-mode toggle, mic button, textarea,
 * send/stop button), relocated verbatim from AssistantChat.jsx (CQ wave-3
 * split). Prop names match the original local identifiers so the JSX is
 * unchanged; the auto-grow onInput handler and the voice-toggle onClick
 * body are byte-identical to the inline originals.
 */
export default function ChatInput({
  attachedFiles, fileInputRef, isStreaming,
  voiceAvailable, voiceMode, setVoiceMode, voice, muteTTS,
  input, setInput, inputRef, handleKeyDown,
  sendMessage, stopStreaming, canSend,
}) {
  return (
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
  )
}
