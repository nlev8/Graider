import Icon from '../Icon'

// Period + date-range filter row for BehaviorPanel (CQ wave-8 split).
// Stateless; filter state lives in the always-mounted shell so values
// survive student expand/collapse cycles. Setters are passed straight
// through and the inline handlers are byte-identical to the pre-split code.
export default function BehaviorFilters({
  periodFilter, setPeriodFilter,
  dateFrom, setDateFrom,
  dateTo, setDateTo,
}) {
  return (
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
  )
}
