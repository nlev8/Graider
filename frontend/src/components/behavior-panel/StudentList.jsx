import Icon from '../Icon'
import StudentEventDetail from './StudentEventDetail'

// Cumulative student list for BehaviorPanel (CQ wave-8 split). Stateless;
// expansion + event-fetch state lives in the always-mounted shell, and the
// loadStudentEvents / handleEmailAction callbacks are passed through with
// their original names so the call sites stay byte-identical.
export default function StudentList({
  cumulativeData, loading,
  expandedStudent, studentEvents, eventsLoading,
  loadStudentEvents, handleEmailAction,
}) {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
      {Object.keys(cumulativeData).length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {Object.values(cumulativeData)
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
                  <StudentEventDetail studentEvents={studentEvents} eventsLoading={eventsLoading} />
                )}
              </div>
            ))}
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 30 }}>
          {loading ? 'Loading...' : 'No behavior data yet'}
        </div>
      )}
    </div>
  )
}
