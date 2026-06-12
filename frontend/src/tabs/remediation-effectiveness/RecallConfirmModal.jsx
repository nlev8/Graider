import React from "react";

/**
 * CQ wave-8 split: Phase 4.2 #5 recall confirm modal, moved verbatim from
 * RemediationEffectiveness.jsx. Stateless — recall state + handlers stay in
 * the shell. The shell's `{recallTarget && (...)}` guard became the
 * early-return-null below (house pattern: guards -> early-return-null);
 * behaviorally identical because this component has no state or effects.
 */
export default function RecallConfirmModal({
  recallTarget, recallError, recallInFlight, closeRecallModal, confirmRecall,
}) {
  if (!recallTarget) return null;
  return (
    <div
      onClick={closeRecallModal}
      style={{
        position: "fixed", inset: 0, zIndex: 9600,
        background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        onClick={function(e) { e.stopPropagation(); }}
        className="glass-card"
        style={{ maxWidth: "440px", width: "100%", padding: "24px" }}
      >
        <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginTop: 0, marginBottom: "12px" }}>
          Recall this remediation?
        </h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
          {(function() {
            var n = (recallTarget.rows || []).filter(function(r) { return r.completed; }).length;
            if (n > 0) {
              return (
                <>
                  <strong>{n} student{n === 1 ? "" : "s"} already submitted</strong>
                  {" " + String.fromCharCode(8212) + " their work is preserved. They'll just no longer see it in their dashboard."}
                </>
              );
            }
            return "Students will no longer see it in their dashboard.";
          })()}
        </p>
        {recallError && (
          <div style={{
            padding: "10px 12px", borderRadius: "6px", marginTop: "12px",
            background: "rgba(239,68,68,0.12)", color: "var(--danger)", fontSize: "0.85rem",
          }}>{recallError}</div>
        )}
        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "20px" }}>
          <button
            onClick={closeRecallModal}
            disabled={recallInFlight}
            className="btn"
            style={{ padding: "8px 16px", fontSize: "0.85rem", opacity: recallInFlight ? 0.5 : 1 }}
          >Cancel</button>
          <button
            onClick={confirmRecall}
            disabled={recallInFlight}
            className="btn"
            style={{
              padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600,
              background: "var(--danger)", color: "white", border: "none",
              opacity: recallInFlight ? 0.6 : 1,
            }}
          >{recallInFlight ? "Recalling..." : "Recall"}</button>
        </div>
      </div>
    </div>
  );
}
