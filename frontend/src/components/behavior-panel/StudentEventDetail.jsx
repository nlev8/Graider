// Expanded per-student event list for BehaviorPanel (CQ wave-8 split).
// Stateless; events/loading state lives in the always-mounted shell.

// Format event time for display
const formatTime = (eventTime) => {
  if (!eventTime) return ''
  try {
    const dt = new Date(eventTime)
    return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  } catch { return '' }
}

export default function StudentEventDetail({ studentEvents, eventsLoading }) {
  return (
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
  )
}
