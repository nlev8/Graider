// CQ wave-8 split: pure display helpers moved verbatim from
// ProgressRankGrid.jsx. btnStyle captured nothing in the component body, so
// hoisting it to module level is a pure move.

export function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: "—" };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

export var btnStyle = function(active) {
  return {
    padding: "6px 14px",
    borderRadius: "8px",
    border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
    background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
    color: active ? "var(--accent-primary)" : "var(--text-secondary)",
    fontSize: "0.85rem",
    fontWeight: 600,
    cursor: "pointer",
  };
};
