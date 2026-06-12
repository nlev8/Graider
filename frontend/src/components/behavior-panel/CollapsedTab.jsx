import Icon from '../Icon'

// Collapsed edge tab for BehaviorPanel (CQ wave-8 split). Stateless; the
// shell owns the collapsed flag and passes the expand handler down.
export default function CollapsedTab({ onExpand }) {
  return (
    <div
      onClick={onExpand}
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
