// CQ wave-8 split: pure display helpers moved verbatim from
// RemediationEffectiveness.jsx (module-level functions, no state).

export function deltaColor(delta) {
  if (delta == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (delta >= 10) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: "+" + delta + "%" };
  if (delta >= 0) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: "+" + delta + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: delta + "%" };
}

export function pctText(pct) {
  if (pct == null) return String.fromCharCode(8212);
  return pct + "%";
}

export function formatDate(iso) {
  if (!iso) return "";
  try {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch (e) {
    return "";
  }
}
