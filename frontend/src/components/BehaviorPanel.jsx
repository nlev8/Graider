import { useState, useCallback, useEffect, useMemo } from 'react'
import Icon from './Icon'
import { useBehaviorStore } from '../hooks/useBehaviorStore'
import { useBehaviorListener } from '../hooks/useBehaviorListener'
import { getAuthHeaders } from '../services/api'

/**
 * BehaviorPanel — collapsible sidebar for the Assistant tab.
 * Tracks classroom behavior (corrections + praise) per student via:
 *   1. Manual add buttons
 *   2. Passive Whisper STT listening (local, FERPA-compliant)
 */
export default function BehaviorPanel({ addToast, voiceModeActive = false }) {
  const store = useBehaviorStore()
  const { state, startSession, endSession, addPending, approvePending,
    editPending, dismissPending, addManualEvent, increment, decrement,
    setViewMode, loadCumulative } = store

  const [collapsed, setCollapsed] = useState(true)
  const [periodInput, setPeriodInput] = useState('')
  const [manualOpen, setManualOpen] = useState(false)
  const [manualName, setManualName] = useState('')
  const [manualType, setManualType] = useState('correction')
  const [manualNote, setManualNote] = useState('')
  const [roster, setRoster] = useState([])
  const [nameFilter, setNameFilter] = useState('')
  const [sttEnabled, setSttEnabled] = useState(false)

  // Load roster for name matching + autocomplete
  useEffect(() => {
    (async () => {
      try {
        const headers = await getAuthHeaders()
        const resp = await fetch('/api/behavior/roster', { headers })
        const data = await resp.json()
        if (Array.isArray(data)) setRoster(data)
        else if (data.roster) setRoster(data.roster)
      } catch { /* roster not critical */ }
    })()
  }, [])

  // Filter roster by period when session is active
  const periodRoster = useMemo(() => {
    if (!state.period) return roster
    const norm = state.period.toLowerCase().replace(/\s+/g, '')
    return roster.filter(s => {
      const sp = (s.period || '').toLowerCase().replace(/\s+/g, '')
      return sp === norm || !state.period
    })
  }, [roster, state.period])

  // Whisper STT hook
  const listener = useBehaviorListener({
    roster: periodRoster,
    period: state.period,
    voiceModeActive,
    onDetection: useCallback((evt) => {
      addPending(evt)
    }, [addPending]),
  })

  // Load cumulative data when switching to cumulative view
  useEffect(() => {
    if (state.viewMode === 'cumulative') {
      loadCumulative({ period: state.period })
    }
  }, [state.viewMode, state.period, loadCumulative])

  // Tally session events by student
  const sessionTally = useMemo(() => {
    const tally = {}
    for (const evt of state.sessionEvents) {
      const key = evt.student_name
      if (!tally[key]) tally[key] = { name: key, student_id: evt.student_id, corrections: 0, praise: 0 }
      if (evt.type === 'correction') tally[key].corrections++
      else tally[key].praise++
    }
    return Object.values(tally).sort((a, b) => b.corrections - a.corrections)
  }, [state.sessionEvents])

  // Handle start/stop session
  const handleToggleSession = useCallback(async () => {
    if (state.sessionActive) {
      // Stop STT if running
      if (listener.isListening) listener.stopListening()
      await endSession()
      if (addToast) addToast('Session saved', 'success')
    } else {
      startSession(periodInput)
    }
  }, [state.sessionActive, periodInput, startSession, endSession, listener, addToast])

  // Toggle STT
  const handleToggleSTT = useCallback(async () => {
    if (listener.isListening) {
      listener.stopListening()
      setSttEnabled(false)
    } else {
      await listener.startListening()
      setSttEnabled(true)
    }
  }, [listener])

  // Manual add
  const handleManualAdd = useCallback(() => {
    if (!manualName.trim()) return
    addManualEvent({
      student_name: manualName.trim(),
      student_id: manualName.trim().toLowerCase().replace(/\s+/g, '_'),
      type: manualType,
      note: manualNote.trim(),
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      period: state.period,
    })
    setManualName('')
    setManualNote('')
    setManualOpen(false)
  }, [manualName, manualType, manualNote, state.period, addManualEvent])

  // Autocomplete matches
  const nameMatches = useMemo(() => {
    if (!manualName.trim()) return []
    const q = manualName.toLowerCase()
    return periodRoster.filter(s => (s.name || '').toLowerCase().includes(q)).slice(0, 5)
  }, [manualName, periodRoster])

  // ─── Collapsed view ───
  if (collapsed) {
    return (
      <div
        onClick={() => setCollapsed(false)}
        style={{
          position: 'absolute', right: 0, top: 8, zIndex: 10,
          background: 'rgba(99,102,241,0.15)', borderRadius: '8px 0 0 8px',
          padding: '8px 10px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', gap: 6, fontSize: 13, color: '#a5b4fc',
          borderRight: 'none', transition: 'background 0.2s',
        }}
        title="Behavior Tracking"
      >
        <Icon name="Activity" size={16} />
        {state.sessionActive && (
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
        )}
      </div>
    )
  }

  // ─── Expanded panel ───
  return (
    <div style={{
      width: 320, minWidth: 320, borderLeft: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(15,15,30,0.6)', display: 'flex', flexDirection: 'column',
      height: '100%', overflow: 'hidden', position: 'relative',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="Activity" size={16} style={{ color: '#a5b4fc' }} />
          <span style={{ fontWeight: 600, fontSize: 14, color: '#e2e8f0' }}>Behavior</span>
          {state.sessionActive && (
            <span style={{
              fontSize: 11, background: 'rgba(34,197,94,0.2)', color: '#4ade80',
              padding: '2px 8px', borderRadius: 10, fontWeight: 500,
            }}>LIVE</span>
          )}
        </div>
        <button onClick={() => setCollapsed(true)} style={{
          background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2,
        }}>
          <Icon name="PanelRightClose" size={16} />
        </button>
      </div>

      {/* Session Controls */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {!state.sessionActive ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input
              value={periodInput}
              onChange={e => setPeriodInput(e.target.value)}
              placeholder="Period (e.g. Period 3)"
              style={{
                background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 6, padding: '6px 10px', color: '#e2e8f0', fontSize: 13, outline: 'none',
              }}
            />
            <button onClick={handleToggleSession} style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff',
              border: 'none', borderRadius: 6, padding: '8px', fontSize: 13,
              fontWeight: 600, cursor: 'pointer',
            }}>
              Start Session
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={handleToggleSTT} style={{
              flex: 1, background: listener.isListening ? 'rgba(239,68,68,0.2)' : 'rgba(99,102,241,0.15)',
              color: listener.isListening ? '#f87171' : '#a5b4fc',
              border: '1px solid ' + (listener.isListening ? 'rgba(239,68,68,0.3)' : 'rgba(99,102,241,0.2)'),
              borderRadius: 6, padding: '6px 8px', fontSize: 12, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
            }}>
              <Icon name={listener.isListening ? 'MicOff' : 'Mic'} size={14} />
              {listener.modelStatus === 'loading' ? 'Loading...' : listener.isListening ? 'Mute' : 'Listen'}
            </button>
            <button onClick={() => setManualOpen(!manualOpen)} style={{
              flex: 1, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
              border: '1px solid rgba(99,102,241,0.2)', borderRadius: 6,
              padding: '6px 8px', fontSize: 12, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
            }}>
              <Icon name="Plus" size={14} />
              Add
            </button>
            <button onClick={handleToggleSession} style={{
              background: 'rgba(239,68,68,0.15)', color: '#f87171',
              border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6,
              padding: '6px 10px', fontSize: 12, cursor: 'pointer',
            }}>
              End
            </button>
          </div>
        )}

        {/* Model loading progress */}
        {listener.modelStatus === 'loading' && (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              Loading Whisper model... {listener.modelProgress}%
            </div>
            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
              <div style={{
                height: '100%', background: '#6366f1', borderRadius: 2,
                width: listener.modelProgress + '%', transition: 'width 0.3s',
              }} />
            </div>
          </div>
        )}

        {/* FERPA disclaimer */}
        {(listener.isListening || listener.modelStatus === 'ready') && (
          <div style={{
            marginTop: 6, fontSize: 10, color: '#64748b', lineHeight: 1.3,
            display: 'flex', alignItems: 'flex-start', gap: 4,
          }}>
            <Icon name="Shield" size={10} style={{ marginTop: 2, flexShrink: 0 }} />
            Audio processed locally. No recordings stored or transmitted.
          </div>
        )}
      </div>

      {/* Manual Add Form */}
      {manualOpen && state.sessionActive && (
        <div style={{
          padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
          background: 'rgba(99,102,241,0.05)',
        }}>
          <div style={{ position: 'relative', marginBottom: 6 }}>
            <input
              value={manualName}
              onChange={e => setManualName(e.target.value)}
              placeholder="Student name"
              style={{
                width: '100%', background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
                padding: '6px 10px', color: '#e2e8f0', fontSize: 13, outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            {nameMatches.length > 0 && manualName.length > 1 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
                background: '#1e1b4b', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '0 0 6px 6px', maxHeight: 150, overflow: 'auto',
              }}>
                {nameMatches.map(s => (
                  <div
                    key={s.student_id || s.name}
                    onClick={() => { setManualName(s.name); }}
                    style={{
                      padding: '6px 10px', fontSize: 13, color: '#e2e8f0',
                      cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.05)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.15)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {s.name} {s.period ? '(' + s.period + ')' : ''}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <button onClick={() => setManualType('correction')} style={{
              flex: 1, padding: '5px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
              background: manualType === 'correction' ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
              color: manualType === 'correction' ? '#f87171' : '#94a3b8',
              border: '1px solid ' + (manualType === 'correction' ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.08)'),
            }}>
              Correction
            </button>
            <button onClick={() => setManualType('praise')} style={{
              flex: 1, padding: '5px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
              background: manualType === 'praise' ? 'rgba(34,197,94,0.2)' : 'rgba(255,255,255,0.06)',
              color: manualType === 'praise' ? '#4ade80' : '#94a3b8',
              border: '1px solid ' + (manualType === 'praise' ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)'),
            }}>
              Praise
            </button>
          </div>
          <input
            value={manualNote}
            onChange={e => setManualNote(e.target.value)}
            placeholder="Note (optional)"
            style={{
              width: '100%', background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
              padding: '6px 10px', color: '#e2e8f0', fontSize: 12, outline: 'none',
              marginBottom: 6, boxSizing: 'border-box',
            }}
            onKeyDown={e => { if (e.key === 'Enter') handleManualAdd() }}
          />
          <button onClick={handleManualAdd} disabled={!manualName.trim()} style={{
            width: '100%', background: manualName.trim() ? '#6366f1' : 'rgba(255,255,255,0.06)',
            color: manualName.trim() ? '#fff' : '#64748b',
            border: 'none', borderRadius: 6, padding: '6px', fontSize: 12,
            cursor: manualName.trim() ? 'pointer' : 'default', fontWeight: 600,
          }}>
            Add Event
          </button>
        </div>
      )}

      {/* Pending Events (from STT) */}
      {state.pendingEvents.length > 0 && (
        <div style={{ padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>
            DETECTED ({state.pendingEvents.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflow: 'auto' }}>
            {state.pendingEvents.map(evt => (
              <div key={evt.id} style={{
                background: 'rgba(255,255,255,0.04)', borderRadius: 6, padding: '8px 10px',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>{evt.student_name}</span>
                  <span style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 4,
                    background: evt.type === 'correction' ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
                    color: evt.type === 'correction' ? '#f87171' : '#4ade80',
                  }}>
                    {evt.type}
                  </span>
                </div>
                {evt.transcript && (
                  <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontStyle: 'italic' }}>
                    "{evt.transcript.slice(0, 80)}"
                  </div>
                )}
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => approvePending(evt.id)} style={{
                    flex: 1, background: 'rgba(34,197,94,0.15)', color: '#4ade80',
                    border: '1px solid rgba(34,197,94,0.2)', borderRadius: 4,
                    padding: '3px', fontSize: 11, cursor: 'pointer',
                  }}>
                    Approve
                  </button>
                  <button onClick={() => {
                    // Toggle type
                    const newType = evt.type === 'correction' ? 'praise' : 'correction'
                    editPending(evt.id, { type: newType })
                  }} style={{
                    background: 'rgba(255,255,255,0.06)', color: '#94a3b8',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 4,
                    padding: '3px 6px', fontSize: 11, cursor: 'pointer',
                  }}>
                    Switch
                  </button>
                  <button onClick={() => dismissPending(evt.id)} style={{
                    background: 'rgba(239,68,68,0.1)', color: '#f87171',
                    border: '1px solid rgba(239,68,68,0.15)', borderRadius: 4,
                    padding: '3px 6px', fontSize: 11, cursor: 'pointer',
                  }}>
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* View Toggle */}
      {state.sessionActive && (
        <div style={{ padding: '6px 14px', display: 'flex', gap: 4 }}>
          {['session', 'cumulative'].map(mode => (
            <button key={mode} onClick={() => setViewMode(mode)} style={{
              flex: 1, padding: '4px', borderRadius: 4, fontSize: 11,
              background: state.viewMode === mode ? 'rgba(99,102,241,0.2)' : 'transparent',
              color: state.viewMode === mode ? '#a5b4fc' : '#64748b',
              border: '1px solid ' + (state.viewMode === mode ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)'),
              cursor: 'pointer', textTransform: 'capitalize',
            }}>
              {mode}
            </button>
          ))}
        </div>
      )}

      {/* Tally Table */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {state.viewMode === 'session' && state.sessionActive ? (
          sessionTally.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {sessionTally.map(s => (
                <div key={s.name} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '6px 10px',
                }}>
                  <span style={{ flex: 1, fontSize: 13, color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.name}
                  </span>
                  {/* Correction counter */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <button onClick={() => decrement(s.name, s.student_id, 'correction')} style={{
                      width: 20, height: 20, borderRadius: 4, border: 'none',
                      background: 'rgba(239,68,68,0.1)', color: '#f87171', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                    }}>-</button>
                    <span style={{ minWidth: 20, textAlign: 'center', fontSize: 13, color: '#f87171', fontWeight: 600 }}>
                      {s.corrections}
                    </span>
                    <button onClick={() => increment(s.name, s.student_id, 'correction')} style={{
                      width: 20, height: 20, borderRadius: 4, border: 'none',
                      background: 'rgba(239,68,68,0.15)', color: '#f87171', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                    }}>+</button>
                  </div>
                  {/* Praise counter */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <button onClick={() => decrement(s.name, s.student_id, 'praise')} style={{
                      width: 20, height: 20, borderRadius: 4, border: 'none',
                      background: 'rgba(34,197,94,0.1)', color: '#4ade80', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                    }}>-</button>
                    <span style={{ minWidth: 20, textAlign: 'center', fontSize: 13, color: '#4ade80', fontWeight: 600 }}>
                      {s.praise}
                    </span>
                    <button onClick={() => increment(s.name, s.student_id, 'praise')} style={{
                      width: 20, height: 20, borderRadius: 4, border: 'none',
                      background: 'rgba(34,197,94,0.15)', color: '#4ade80', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                    }}>+</button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 30 }}>
              <Icon name="Activity" size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
              <div>No events yet</div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                Use the Listen or Add buttons above
              </div>
            </div>
          )
        ) : state.viewMode === 'cumulative' ? (
          Object.keys(state.cumulativeData).length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.values(state.cumulativeData)
                .sort((a, b) => (b.total_corrections || 0) - (a.total_corrections || 0))
                .map(s => (
                  <div key={s.name} style={{
                    background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '8px 10px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>{s.name}</span>
                      <div style={{ display: 'flex', gap: 8, fontSize: 12 }}>
                        <span style={{ color: '#f87171' }}>{s.total_corrections || 0} corrections</span>
                        <span style={{ color: '#4ade80' }}>{s.total_praise || 0} praise</span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 30 }}>
              No cumulative data yet
            </div>
          )
        ) : !state.sessionActive ? (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 30 }}>
            <Icon name="Activity" size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>Start a session to begin tracking</div>
            <div style={{ fontSize: 11, marginTop: 4, lineHeight: 1.4 }}>
              Enter the class period above and click Start Session.
              Use Listen for passive voice detection or Add for manual entry.
            </div>
          </div>
        ) : null}
      </div>

      {/* Last transcript indicator */}
      {listener.isListening && listener.lastTranscript && (
        <div style={{
          padding: '6px 14px', borderTop: '1px solid rgba(255,255,255,0.06)',
          fontSize: 10, color: '#64748b', fontStyle: 'italic',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          Last heard: "{listener.lastTranscript.slice(0, 60)}"
        </div>
      )}

      {/* Error display */}
      {state.error && (
        <div style={{
          padding: '6px 14px', borderTop: '1px solid rgba(239,68,68,0.2)',
          fontSize: 11, color: '#f87171', background: 'rgba(239,68,68,0.05)',
        }}>
          {state.error}
        </div>
      )}
    </div>
  )
}
