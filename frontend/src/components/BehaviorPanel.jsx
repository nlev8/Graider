import { useState, useCallback, useEffect, useMemo } from 'react'
import Icon from './Icon'
import { useBehaviorStore } from '../hooks/useBehaviorStore'
// import { useBehaviorListener } from '../hooks/useBehaviorListener'
import { getAuthHeaders } from '../services/api'

/**
 * BehaviorPanel — collapsible sidebar for the Assistant tab.
 * Shows cumulative behavior data with event detail + email actions.
 * Live session tracking (STT, manual entry) is commented out — phone app handles that.
 */
export default function BehaviorPanel({ addToast /*, voiceModeActive = false */ }) {
  const store = useBehaviorStore()
  const { state, loadCumulative } = store

  const [collapsed, setCollapsed] = useState(true)

  // Event detail state
  const [expandedStudent, setExpandedStudent] = useState(null)
  const [studentEvents, setStudentEvents] = useState([])
  const [eventsLoading, setEventsLoading] = useState(false)

  // Date range filter state
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // Period filter
  const [periodFilter, setPeriodFilter] = useState('')

  /*
  // ── Live session tracking (commented out — phone app handles this) ──
  const [periodInput, setPeriodInput] = useState('')
  const [manualOpen, setManualOpen] = useState(false)
  const [manualName, setManualName] = useState('')
  const [manualType, setManualType] = useState('correction')
  const [manualNote, setManualNote] = useState('')
  const [roster, setRoster] = useState([])
  const [sttEnabled, setSttEnabled] = useState(false)

  const { startSession, endSession, addPending, approvePending,
    editPending, dismissPending, addManualEvent, increment, decrement,
    setViewMode } = store

  // Load roster for name matching + autocomplete
  useEffect(() => {
    (async () => {
      try {
        const headers = await getAuthHeaders()
        const resp = await fetch('/api/behavior/roster', { headers })
        const data = await resp.json()
        if (Array.isArray(data)) setRoster(data)
        else if (data.roster) setRoster(data.roster)
      } catch {}
    })()
  }, [])

  const periodRoster = useMemo(() => {
    if (!state.period) return roster
    const norm = state.period.toLowerCase().replace(/\s+/g, '')
    return roster.filter(s => {
      const sp = (s.period || '').toLowerCase().replace(/\s+/g, '')
      return sp === norm || !state.period
    })
  }, [roster, state.period])

  const listener = useBehaviorListener({
    roster: periodRoster,
    period: state.period,
    voiceModeActive,
    onDetection: useCallback((evt) => { addPending(evt) }, [addPending]),
  })

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

  const handleToggleSession = useCallback(async () => {
    if (state.sessionActive) {
      if (listener.isListening) listener.stopListening()
      await endSession()
      if (addToast) addToast('Session saved', 'success')
    } else {
      startSession(periodInput)
      setViewMode('session')
    }
  }, [state.sessionActive, periodInput, startSession, endSession, listener, addToast, setViewMode])

  const handleToggleSTT = useCallback(async () => {
    if (listener.isListening) { listener.stopListening(); setSttEnabled(false) }
    else { await listener.startListening(); setSttEnabled(true) }
  }, [listener])

  const handleManualAdd = useCallback(() => {
    if (!manualName.trim()) return
    addManualEvent({
      student_name: manualName.trim(),
      student_id: manualName.trim().toLowerCase().replace(/\s+/g, '_'),
      type: manualType, note: manualNote.trim(),
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      period: state.period,
    })
    setManualName(''); setManualNote(''); setManualOpen(false)
  }, [manualName, manualType, manualNote, state.period, addManualEvent])

  const nameMatches = useMemo(() => {
    if (!manualName.trim()) return []
    const q = manualName.toLowerCase()
    return periodRoster.filter(s => (s.name || '').toLowerCase().includes(q)).slice(0, 5)
  }, [manualName, periodRoster])
  // ── End live session tracking ──
  */

  // Load cumulative data on mount and when filters change
  useEffect(() => {
    loadCumulative({ period: periodFilter, date_from: dateFrom, date_to: dateTo })
  }, [periodFilter, dateFrom, dateTo, loadCumulative])

  // Load individual events for a student
  const loadStudentEvents = useCallback(async (studentName) => {
    if (expandedStudent === studentName) {
      setExpandedStudent(null)
      setStudentEvents([])
      return
    }
    setExpandedStudent(studentName)
    setEventsLoading(true)
    try {
      const headers = await getAuthHeaders()
      const params = new URLSearchParams({ student_name: studentName, limit: '50' })
      if (periodFilter) params.set('period', periodFilter)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      const resp = await fetch('/api/behavior/events?' + params.toString(), { headers })
      const data = await resp.json()
      if (data.status === 'success') {
        setStudentEvents(data.data.events || [])
      } else {
        setStudentEvents([])
      }
    } catch {
      setStudentEvents([])
    } finally {
      setEventsLoading(false)
    }
  }, [expandedStudent, periodFilter, dateFrom, dateTo])

  // Email quick action — dispatch event to AssistantChat
  const handleEmailAction = useCallback((studentName) => {
    window.dispatchEvent(new CustomEvent('behavior-email-request', {
      detail: { message: 'Generate a behavior email for ' + studentName }
    }))
    if (addToast) addToast('Email request sent to assistant', 'info')
  }, [addToast])

  // Format event time for display
  const formatTime = (eventTime) => {
    if (!eventTime) return ''
    try {
      const dt = new Date(eventTime)
      return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
    } catch { return '' }
  }

  // ─── Collapsed view ───
  if (collapsed) {
    return (
      <div
        onClick={() => setCollapsed(false)}
        style={{
          position: 'absolute', right: 0, top: 60, zIndex: 10,
          background: 'rgba(99,102,241,0.15)', borderRadius: '8px 0 0 8px',
          padding: '8px 10px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', gap: 6, fontSize: 13, color: '#a5b4fc',
          borderRight: 'none', transition: 'background 0.2s',
        }}
        title="Behavior Tracking"
      >
        <Icon name="Activity" size={16} />
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
        </div>
        <button onClick={() => setCollapsed(true)} style={{
          background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2,
        }}>
          <Icon name="PanelRightClose" size={16} />
        </button>
      </div>

      {/* Filters */}
      <div style={{ padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <input
          value={periodFilter}
          onChange={e => setPeriodFilter(e.target.value)}
          placeholder="Filter by period"
          style={{
            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 6, padding: '5px 8px', color: '#e2e8f0', fontSize: 12, outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            style={{
              flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4, padding: '3px 6px', color: '#e2e8f0', fontSize: 11, outline: 'none',
              colorScheme: 'dark',
            }}
            title="From date"
          />
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            style={{
              flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4, padding: '3px 6px', color: '#e2e8f0', fontSize: 11, outline: 'none',
              colorScheme: 'dark',
            }}
            title="To date"
          />
          {(dateFrom || dateTo || periodFilter) && (
            <button onClick={() => { setDateFrom(''); setDateTo(''); setPeriodFilter('') }} style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 4, padding: '3px 6px', color: '#94a3b8', fontSize: 11, cursor: 'pointer',
            }} title="Clear filters">
              <Icon name="X" size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Student List */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {Object.keys(state.cumulativeData).length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.values(state.cumulativeData)
              .sort((a, b) => (b.total_corrections || 0) - (a.total_corrections || 0))
              .map(s => (
                <div key={s.name}>
                  {/* Student row */}
                  <div style={{
                    background: expandedStudent === s.name ? 'rgba(99,102,241,0.1)' : 'rgba(255,255,255,0.03)',
                    borderRadius: expandedStudent === s.name ? '6px 6px 0 0' : 6,
                    padding: '8px 10px', cursor: 'pointer',
                    border: expandedStudent === s.name ? '1px solid rgba(99,102,241,0.2)' : 'none',
                    borderBottom: expandedStudent === s.name ? 'none' : undefined,
                  }} onClick={() => loadStudentEvents(s.name)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                        <Icon name={expandedStudent === s.name ? 'ChevronDown' : 'ChevronRight'} size={12} style={{ color: '#64748b', flexShrink: 0 }} />
                        <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                        <span style={{ color: '#f87171', fontSize: 12 }}>{s.total_corrections || 0}</span>
                        <span style={{ color: '#4ade80', fontSize: 12 }}>{s.total_praise || 0}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEmailAction(s.name) }}
                          style={{
                            background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.2)',
                            borderRadius: 4, padding: '2px 5px', cursor: 'pointer', display: 'flex',
                            alignItems: 'center', color: '#a5b4fc',
                          }}
                          title={'Generate email for ' + s.name}
                        >
                          <Icon name="Mail" size={12} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded event detail */}
                  {expandedStudent === s.name && (
                    <div style={{
                      background: 'rgba(99,102,241,0.05)',
                      border: '1px solid rgba(99,102,241,0.2)',
                      borderTop: 'none', borderRadius: '0 0 6px 6px',
                      padding: '6px 8px', maxHeight: 300, overflow: 'auto',
                    }}>
                      {eventsLoading ? (
                        <div style={{ textAlign: 'center', color: '#64748b', fontSize: 11, padding: 12 }}>
                          Loading events...
                        </div>
                      ) : studentEvents.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {studentEvents.map((evt, i) => (
                            <div key={evt.id || i} style={{
                              background: 'rgba(255,255,255,0.03)', borderRadius: 4, padding: '6px 8px',
                              borderLeft: '2px solid ' + (evt.type === 'correction' ? '#f87171' : '#4ade80'),
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                                  <span style={{
                                    fontSize: 9, padding: '1px 4px', borderRadius: 3, fontWeight: 600,
                                    background: evt.type === 'correction' ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
                                    color: evt.type === 'correction' ? '#f87171' : '#4ade80',
                                    textTransform: 'uppercase',
                                  }}>{evt.type}</span>
                                  {evt.source && evt.source !== 'manual' && (
                                    <span style={{
                                      fontSize: 9, padding: '1px 4px', borderRadius: 3,
                                      background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
                                    }}>{evt.source}</span>
                                  )}
                                </div>
                                <span style={{ fontSize: 10, color: '#64748b' }}>
                                  {evt.date} {formatTime(evt.event_time)}
                                </span>
                              </div>
                              {evt.note && (
                                <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 2 }}>{evt.note}</div>
                              )}
                              {evt.transcript && (
                                <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2, fontStyle: 'italic' }}>
                                  "{evt.transcript.length > 100 ? evt.transcript.slice(0, 100) + '...' : evt.transcript}"
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ textAlign: 'center', color: '#64748b', fontSize: 11, padding: 8 }}>
                          No individual events found
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 30 }}>
            {state.loading ? 'Loading...' : 'No behavior data yet'}
          </div>
        )}
      </div>

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
