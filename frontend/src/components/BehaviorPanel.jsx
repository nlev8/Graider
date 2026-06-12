import { useState, useCallback, useEffect, useMemo } from 'react'
import { useBehaviorStore } from '../hooks/useBehaviorStore'
// import { useBehaviorListener } from '../hooks/useBehaviorListener'
import { getAuthHeaders } from '../services/api'
import CollapsedTab from './behavior-panel/CollapsedTab'
import PanelHeader from './behavior-panel/PanelHeader'
import BehaviorFilters from './behavior-panel/BehaviorFilters'
import StudentList from './behavior-panel/StudentList'

/**
 * BehaviorPanel — collapsible sidebar for the Assistant tab.
 * Shows cumulative behavior data with event detail + email actions.
 * Live session tracking (STT, manual entry) is commented out — phone app handles that.
 *
 * Shell for the CQ wave-8 split: owns ALL state (collapse flag, filters,
 * expanded student + fetched events) and the data/event handlers — including
 * the `behavior-email-request` dispatch consumed by assistant-chat's
 * useAssistantChat listener — so the stateless children in behavior-panel/
 * only render what they're handed.
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

  // ─── Collapsed view ───
  if (collapsed) {
    return <CollapsedTab onExpand={() => setCollapsed(false)} />
  }

  // ─── Expanded panel ───
  return (
    <div style={{
      width: 320, minWidth: 320, borderLeft: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(15,15,30,0.6)', display: 'flex', flexDirection: 'column',
      height: '100%', overflow: 'hidden', position: 'relative',
    }}>
      <PanelHeader onCollapse={() => setCollapsed(true)} />

      <BehaviorFilters
        periodFilter={periodFilter} setPeriodFilter={setPeriodFilter}
        dateFrom={dateFrom} setDateFrom={setDateFrom}
        dateTo={dateTo} setDateTo={setDateTo}
      />

      <StudentList
        cumulativeData={state.cumulativeData}
        loading={state.loading}
        expandedStudent={expandedStudent}
        studentEvents={studentEvents}
        eventsLoading={eventsLoading}
        loadStudentEvents={loadStudentEvents}
        handleEmailAction={handleEmailAction}
      />

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
