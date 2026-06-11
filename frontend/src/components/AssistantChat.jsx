import { useMemo } from 'react'
import Icon from './Icon'
import { getSubjectPrompts, ACCEPTED_FILE_TYPES } from './assistant-chat/prompts'
import useAssistantChat from './assistant-chat/useAssistantChat'
import ChatHeader from './assistant-chat/ChatHeader'
import EmptyState from './assistant-chat/EmptyState'
import MessageBubble from './assistant-chat/MessageBubble'
import AttachmentChips from './assistant-chat/AttachmentChips'
import ChatInput from './assistant-chat/ChatInput'

/*
 * AssistantChat — thin orchestrator after the CQ wave-3 split of the
 * former 1,060-line component function into ./assistant-chat/* (wave-1/2
 * tabs/analytics + tabs/grade + planner-lesson precedent). All state,
 * refs, effects, and handlers live in useAssistantChat (called
 * unconditionally; this component is always-mounted from App.jsx, so the
 * SSE stream + abort/scroll refs keep their pre-split lifecycle).
 * Exported API unchanged: default export, props { addToast, subject }.
 */
export default function AssistantChat({ addToast, subject }) {
  const { suggested: SUGGESTED_PROMPTS, more: MORE_PROMPTS } = useMemo(
    () => getSubjectPrompts(subject), [subject]
  )
  const {
    messages, setMessages,
    input, setInput,
    isStreaming,
    showMorePrompts, setShowMorePrompts,
    attachedFiles,
    voiceMode, setVoiceMode,
    voiceAvailable,
    sessionCost,
    messagesEndRef, inputRef, fileInputRef,
    voice,
    handleFileSelect, removeAttachedFile,
    muteTTS, sendMessage, stopStreaming,
    clearConversation, clearMemory, handleKeyDown,
  } = useAssistantChat({ addToast })

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
      <ChatHeader
        sessionCost={sessionCost}
        hasMessages={hasMessages}
        clearConversation={clearConversation}
        clearMemory={clearMemory}
      />

      {/* Messages Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <EmptyState
          hasMessages={hasMessages}
          SUGGESTED_PROMPTS={SUGGESTED_PROMPTS}
          MORE_PROMPTS={MORE_PROMPTS}
          showMorePrompts={showMorePrompts}
          setShowMorePrompts={setShowMorePrompts}
          sendMessage={sendMessage}
        />

        {messages.map((msg, idx) => (
          <MessageBubble
            key={idx}
            msg={msg}
            idx={idx}
            messages={messages}
            isStreaming={isStreaming}
            voice={voice}
            setMessages={setMessages}
            addToast={addToast}
          />
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
      <AttachmentChips attachedFiles={attachedFiles} removeAttachedFile={removeAttachedFile} />

      {/* Input Area */}
      <ChatInput
        attachedFiles={attachedFiles}
        fileInputRef={fileInputRef}
        isStreaming={isStreaming}
        voiceAvailable={voiceAvailable}
        voiceMode={voiceMode}
        setVoiceMode={setVoiceMode}
        voice={voice}
        muteTTS={muteTTS}
        input={input}
        setInput={setInput}
        inputRef={inputRef}
        handleKeyDown={handleKeyDown}
        sendMessage={sendMessage}
        stopStreaming={stopStreaming}
        canSend={canSend}
      />
    </div>
  )
}
