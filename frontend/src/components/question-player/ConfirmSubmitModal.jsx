import React from "react";

// Submit-confirmation / time's-up modal — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). The render guard (showConfirmModal)
// moved inside as an early return, per house precedent. data-testids are
// pinned by the e2e student-flow specs; do not change them.
export default function ConfirmSubmitModal({
  show,
  timedOut,
  answeredCount,
  totalQuestions,
  lm,
  theme,
  onCancel,
  onConfirm,
}) {
  if (!show) return null;

  var subtextColor = theme.subtextColor;
  var borderClr = theme.borderClr;

  return (
    <div style={{
      position: "fixed",
      top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0, 0, 0, 0.85)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000,
    }}>
      <div style={{
        background: lm ? "white" : "rgba(30, 30, 60, 0.95)",
        border: "1px solid " + borderClr,
        borderRadius: "16px",
        padding: "30px",
        maxWidth: "400px",
        width: "90%",
        textAlign: "center",
      }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "15px" }}>
          {timedOut ? "Time's Up!" : "Submit?"}
        </h2>
        <p style={{ color: subtextColor, marginBottom: "8px" }}>
          {"You answered " + answeredCount + " of " + totalQuestions + " questions."}
        </p>
        {answeredCount < totalQuestions && (
          <p style={{ color: "#f59e0b", fontSize: "0.9rem", marginBottom: "20px" }}>
            {(totalQuestions - answeredCount) + " question" + (totalQuestions - answeredCount !== 1 ? "s" : "") + " unanswered"}
          </p>
        )}
        <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
          {!timedOut && (
            <button
              onClick={onCancel}
              data-testid="btn-go-back"
              style={{
                padding: "12px 24px",
                fontSize: "1rem",
                fontWeight: 600,
                border: "2px solid var(--glass-border)",
                borderRadius: "10px",
                cursor: "pointer",
                background: "var(--glass-bg)",
                color: "var(--text-primary)",
              }}
            >
              Go Back
            </button>
          )}
          <button
            onClick={onConfirm}
            data-testid="btn-confirm-submit"
            style={{
              padding: "12px 24px",
              fontSize: "1rem",
              fontWeight: 600,
              border: "none",
              borderRadius: "10px",
              cursor: "pointer",
              background: "linear-gradient(135deg, #22c55e, #16a34a)",
              color: "white",
            }}
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
}
