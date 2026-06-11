import React from "react";
import Icon from "../../components/Icon";

/*
 * Error Alert Banner — relocated verbatim from GradeTab.jsx (CQ wave-2 split).
 * `{status.error && (...)}` at the call site became the early-return-null below
 * (house precedent from the wave-1 tabs/analytics + tabs/results splits).
 */
export default function ErrorBanner({ status, setStatus }) {
  if (!status.error) return null;
  return (
    <div
      className="glass-card fade-in"
      style={{
        padding: "15px 20px",
        marginBottom: "20px",
        background: "rgba(248,113,113,0.1)",
        border: "1px solid rgba(248,113,113,0.4)",
        display: "flex",
        alignItems: "center",
        gap: "12px",
      }}
    >
      <Icon
        name="AlertTriangle"
        size={24}
        style={{ color: "#f87171" }}
      />
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontWeight: 600,
            color: "#f87171",
            marginBottom: "4px",
          }}
        >
          Grading Stopped - Error Detected
        </div>
        <div
          style={{
            fontSize: "0.9rem",
            color: "var(--text-secondary)",
          }}
        >
          {status.error}
        </div>
      </div>
      <button
        onClick={() =>
          setStatus((prev) => ({ ...prev, error: null }))
        }
        style={{
          background: "rgba(248,113,113,0.2)",
          border: "none",
          borderRadius: "8px",
          padding: "8px 12px",
          color: "#f87171",
          cursor: "pointer",
          fontSize: "0.85rem",
          fontWeight: 500,
        }}
      >
        Dismiss
      </button>
    </div>
  );
}
