import React from "react";

/*
 * Grading progress bar + session-cost line — relocated verbatim from
 * GradeTab.jsx (CQ wave-2 split). `{status.is_running && (...)}` at the call
 * site became the early-return-null below; the `pct` computation moved here
 * with it (it was only consumed by this block).
 */
export default function GradingProgress({ status }) {
  if (!status.is_running) return null;
  const pct = status.total > 0 ? (status.progress / status.total) * 100 : 0;
  return (
    <div style={{ marginTop: "20px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "8px",
          fontSize: "0.9rem",
        }}
      >
        <span>Progress</span>
        <span>
          {status.progress}/{status.total}
        </span>
      </div>
      <div
        style={{
          height: "8px",
          background: "var(--btn-secondary-bg)",
          borderRadius: "4px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background:
              "linear-gradient(90deg, #6366f1, #8b5cf6)",
            transition: "width 0.3s",
          }}
        />
      </div>
      {status.current_file && (
        <p
          style={{
            marginTop: "8px",
            fontSize: "0.85rem",
            color: "var(--text-secondary)",
          }}
        >
          {status.current_file}
        </p>
      )}
      {status.session_cost && status.session_cost.total_cost > 0 && (
        <div style={{
          display: "flex", gap: "16px", fontSize: "0.8rem",
          color: "var(--text-secondary)", marginTop: "8px"
        }}>
          <span>Cost: ${status.session_cost.total_cost.toFixed(4)}</span>
          <span>Tokens: {(status.session_cost.total_input_tokens + status.session_cost.total_output_tokens).toLocaleString()}</span>
          <span>API Calls: {status.session_cost.total_api_calls}</span>
        </div>
      )}
    </div>
  );
}
