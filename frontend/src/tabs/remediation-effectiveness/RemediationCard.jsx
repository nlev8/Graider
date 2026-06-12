import React from "react";
import { deltaColor, pctText, formatDate } from "./helpers";

/**
 * CQ wave-8 split: one per-remediation card (header + before/after table +
 * DOK expander rows), moved verbatim from RemediationEffectiveness.jsx.
 * Stateless — all state (expandedDokKey, recall, drawer) stays in the shell;
 * prop names match the shell's identifiers so the JSX body is a pure move.
 */
export default function RemediationCard({
  rem, expandedDokKey, setExpandedDokKey, openRecallModal, openRemediateAgain,
}) {
  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
        <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0 }}>{rem.title}</h4>
        <span style={{
          fontFamily: "monospace", fontSize: "0.78rem", padding: "3px 8px",
          borderRadius: "6px", background: "rgba(99,102,241,0.15)",
          color: "var(--accent-primary)", fontWeight: 600,
        }}>{rem.standard_code}</span>
        <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Published {formatDate(rem.created_at)} {String.fromCharCode(8226)} {rem.target_count} student{rem.target_count === 1 ? "" : "s"}
        </span>
        {/* Phase 4.2 #5: Recall button (or Recalled badge if already inactive). */}
        <div style={{ marginLeft: "auto" }}>
          {rem.is_active === false ? (
            <span style={{
              fontSize: "0.78rem", padding: "3px 10px", borderRadius: "6px",
              background: "rgba(239,68,68,0.12)", color: "var(--danger)", fontWeight: 700,
            }}>Recalled</span>
          ) : (
            <button
              onClick={function() { openRecallModal(rem); }}
              className="btn"
              style={{
                padding: "5px 12px", fontSize: "0.8rem", fontWeight: 600,
                background: "transparent", color: "var(--danger)",
                border: "1px solid var(--danger)",
              }}
            >Recall</button>
          )}
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr>
              <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "8px 12px", textAlign: "left", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>Student</th>
              <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>Before</th>
              <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>After</th>
              <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>{String.fromCharCode(916)}</th>
              <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "100px" }}>Completed</th>
              <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>Attempts</th>
              <th style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "150px" }}></th>
            </tr>
          </thead>
          <tbody>
            {(rem.rows || []).map(function(row) {
              var d = deltaColor(row.delta);
              var beforeBadge = row.before == null
                ? <span style={{ fontSize: "0.72rem", padding: "2px 6px", borderRadius: "4px", background: "var(--glass-bg)", color: "var(--text-muted)" }}>No baseline</span>
                : pctText(row.before);
              // Phase 4.3 Sprint 3: per-DOK split expander.
              // JSON serializes int dict keys to strings (Codex MINOR);
              // union the keys, sort numerically.
              var beforeDok = row.before_by_dok || {};
              var afterDok = row.after_by_dok || {};
              var deltaDok = row.delta_by_dok || {};
              var dokKeys = {};
              Object.keys(beforeDok).forEach(function(k) { dokKeys[k] = true; });
              Object.keys(afterDok).forEach(function(k) { dokKeys[k] = true; });
              var sortedDoks = Object.keys(dokKeys).sort(function(a, b) {
                return parseInt(a, 10) - parseInt(b, 10);
              });
              var hasDok = sortedDoks.length > 0;
              var dokKey = rem.remediation_id + ":" + row.student_id;
              var isDokExpanded = expandedDokKey === dokKey;
              return (
                <React.Fragment key={row.student_id}>
                <tr>
                  <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 12px", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>
                    {row.student_name || "(unknown)"}
                    {hasDok && (
                      <button
                        type="button"
                        onClick={function() {
                          setExpandedDokKey(isDokExpanded ? null : dokKey);
                        }}
                        style={{
                          background: "transparent", border: "none",
                          color: "var(--accent-primary)", fontSize: "0.7rem",
                          cursor: "pointer", padding: "2px 0", marginLeft: "8px",
                          fontWeight: 600,
                        }}
                      >{isDokExpanded ? String.fromCharCode(9662) + " DOK" : String.fromCharCode(9656) + " DOK"}</button>
                    )}
                  </td>
                  <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{beforeBadge}</td>
                  <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{pctText(row.after)}</td>
                  <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>
                    <span style={{
                      display: "inline-block", padding: "3px 10px", borderRadius: "6px",
                      background: d.bg, color: d.text, fontWeight: 700, fontSize: "0.82rem",
                    }}>{d.label}</span>
                  </td>
                  <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>
                    {row.completed
                      ? <span style={{ color: "var(--success)", fontWeight: 600 }}>Yes</span>
                      : <span style={{ color: "var(--text-muted)" }}>No</span>}
                  </td>
                  <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{row.attempt_count}</td>
                  <td style={{ padding: "10px", textAlign: "right", borderBottom: "1px solid var(--glass-border)" }}>
                    <button
                      onClick={function() { openRemediateAgain(row.student_id, row.student_name, rem.standard_code); }}
                      className="btn"
                      style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
                    >Remediate again</button>
                  </td>
                </tr>
                {isDokExpanded && hasDok && (
                  <tr>
                    <td colSpan={7} style={{
                      padding: "10px 16px", borderBottom: "1px solid var(--glass-border)",
                      background: "rgba(99,102,241,0.05)",
                    }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        {sortedDoks.map(function(dokKeyStr) {
                          var bPct = beforeDok[dokKeyStr];
                          var aPct = afterDok[dokKeyStr];
                          var dPct = deltaDok[dokKeyStr];
                          var bText = (typeof bPct === "number") ? (bPct + "%") : String.fromCharCode(8212);
                          var aText = (typeof aPct === "number") ? (aPct + "%") : String.fromCharCode(8212);
                          var dText = (typeof dPct === "number")
                            ? ((dPct > 0 ? "+" : "") + dPct)
                            : String.fromCharCode(8212);
                          var dColor = (typeof dPct === "number")
                            ? (dPct > 0 ? "var(--success)" : (dPct < 0 ? "var(--danger)" : "var(--text-muted)"))
                            : "var(--text-muted)";
                          return (
                            <div key={dokKeyStr} style={{ display: "flex", gap: "12px", fontSize: "0.78rem", alignItems: "center" }}>
                              <span style={{ width: "60px", fontWeight: 600, color: "var(--accent-primary)" }}>{"DOK " + dokKeyStr}</span>
                              <span style={{ width: "70px", color: "var(--text-secondary)" }}>{bText}</span>
                              <span style={{ color: "var(--text-muted)" }}>{String.fromCharCode(8594)}</span>
                              <span style={{ width: "70px", color: "var(--text-secondary)" }}>{aText}</span>
                              <span style={{ color: dColor, fontWeight: 700 }}>{dText}</span>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
