import React from "react";
import Icon from "../Icon";

// Live run progress view. Originally the `if (view === "run" && runStatus)`
// branch of AutomationBuilder — markup relocated verbatim (CQ wave-6 split);
// the conditional render became the early-return guard below. Run state,
// polling, and stop/back handlers stay in the AutomationBuilder shell.
export default function AutomationRunView(props) {
  const { view, runStatus, stopRun, setView, loadList } = props;
  if (!(view === "run" && runStatus)) return null;

  const pct = runStatus.total_steps > 0 ? Math.round((runStatus.current_step / runStatus.total_steps) * 100) : 0;
  const isDone = runStatus.status !== "running";
  return (
      <div style={{ padding: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: 10, margin: 0 }}>
            <Icon name="Play" size={24} /> Running Automation
          </h2>
          <div style={{ display: "flex", gap: 8 }}>
            {!isDone && (
              <button onClick={stopRun} style={{
                background: "#ef4444", color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
              }}>
                Stop
              </button>
            )}
            <button onClick={() => { setView("list"); loadList(); }} style={{
              background: "var(--card-bg)", color: "var(--text-primary)", border: "1px solid var(--glass-border)",
              borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            }}>
              Back
            </button>
          </div>
        </div>

        <div style={{
          background: "var(--card-bg)", borderRadius: 12, padding: 20,
          border: "1px solid var(--glass-border)", marginBottom: 16,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>
              {isDone ? (runStatus.status === "error" ? "Error" : "Complete") : "Step " + runStatus.current_step + " of " + runStatus.total_steps}
            </span>
            <span style={{ color: "var(--text-secondary)" }}>{pct}%</span>
          </div>
          <div style={{ background: "var(--glass-border)", borderRadius: 6, height: 8, overflow: "hidden" }}>
            <div style={{
              background: runStatus.status === "error" ? "#ef4444" : isDone ? "#22c55e" : "var(--accent-primary)",
              height: "100%", width: (isDone ? 100 : pct) + "%", transition: "width 0.3s",
              borderRadius: 6,
            }} />
          </div>
          <p style={{ marginTop: 10, fontSize: "0.9rem", color: "var(--text-secondary)" }}>{runStatus.message}</p>
        </div>

        <div style={{
          background: "#0f172a", color: "#e2e8f0", borderRadius: 12, padding: 16,
          fontFamily: "monospace", fontSize: "0.8rem", maxHeight: 400, overflowY: "auto",
        }}>
          {(runStatus.log || []).map((entry, i) => {
            const color = entry.type === "step_error" || entry.type === "error" ? "#f87171"
              : entry.type === "step_done" || entry.type === "done" ? "#4ade80"
              : entry.type === "step_start" ? "#60a5fa" : "#94a3b8";
            return (
              <div key={i} style={{ color, marginBottom: 2 }}>
                [{entry.type}] {entry.label || entry.message || ""}
              </div>
            );
          })}
          {(runStatus.log || []).length === 0 && <div style={{ color: "#94a3b8" }}>Waiting for output...</div>}
        </div>
      </div>
  );
}
