import Icon from '../Icon'

// Expanded-panel header for BehaviorPanel (CQ wave-8 split). Stateless; the
// shell owns the collapsed flag and passes the collapse handler down.
export default function PanelHeader({ onCollapse }) {
  return (
    <div style={{
      padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name="Activity" size={16} style={{ color: '#a5b4fc' }} />
        <span style={{ fontWeight: 600, fontSize: 14, color: '#e2e8f0' }}>Behavior</span>
      </div>
      <button onClick={onCollapse} style={{
        background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2,
      }}>
        <Icon name="PanelRightClose" size={16} />
      </button>
    </div>
  )
}
