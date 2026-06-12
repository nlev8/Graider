import React from "react";

/**
 * CQ wave-8 split: the mastery-cell popover (contributing submissions +
 * <85% remediation CTA), moved verbatim from ProgressRankGrid.jsx.
 * Stateless — selectedCell/remediation state stays in the shell. The
 * shell's `{selectedCell && (...)}` guard became the early-return-null
 * below (house pattern: guards -> early-return-null); behaviorally
 * identical because this component has no state or effects.
 */
export default function CellPopover({ selectedCell, setSelectedCell, setRemediationTrigger }) {
  if (!selectedCell) return null;
  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "var(--modal-bg)", display: "flex", alignItems: "center",
        justifyContent: "center", zIndex: 9999, padding: "20px",
      }}
      onClick={function() { setSelectedCell(null); }}
    >
      <div
        className="glass-card"
        style={{ maxWidth: "500px", width: "100%", padding: "24px", borderRadius: "16px" }}
        onClick={function(e) { e.stopPropagation(); }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
          <div>
            <h4 style={{ fontSize: "1rem", fontWeight: 700 }}>{selectedCell.student.student_name}</h4>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>{selectedCell.standard}</p>
          </div>
          <button onClick={function() { setSelectedCell(null); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
            {String.fromCharCode(10005)}
          </button>
        </div>
        <div style={{ fontSize: "0.85rem", marginBottom: "10px" }}>
          Mastery: <strong>{selectedCell.mastery.percentage}%</strong> ({selectedCell.mastery.points_earned}/{selectedCell.mastery.points_possible} pts across {selectedCell.mastery.question_count} questions)
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
          Contributing submissions
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "300px", overflowY: "auto" }}>
          {(selectedCell.mastery.contributing_submissions || []).map(function(c, i) {
            return (
              <div key={i} style={{ padding: "8px 12px", background: "var(--glass-bg)", borderRadius: "6px", fontSize: "0.8rem" }}>
                <div style={{ fontWeight: 600 }}>{c.title}</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                  {c.attempt_number ? 'Attempt ' + c.attempt_number + ' ' + String.fromCharCode(8226) + ' ' : ''}
                  {c.points_earned}/{c.points_possible} pts
                </div>
              </div>
            );
          })}
        </div>
        {selectedCell.mastery && selectedCell.mastery.percentage < 85 && (
          <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid var(--glass-border)" }}>
            <button
              onClick={function() {
                setRemediationTrigger({
                  standardCode: selectedCell.standard,
                  targetMode: "single_student",
                  targetStudentId: selectedCell.student.student_id,
                  targetStudentName: selectedCell.student.student_name,
                });
                setSelectedCell(null);
              }}
              className="btn btn-primary"
              style={{ width: "100%", padding: "8px", fontSize: "0.85rem" }}
            >
              Generate remediation
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
