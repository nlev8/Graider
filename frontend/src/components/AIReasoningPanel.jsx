/**
 * AIReasoningPanel — debug/inspection panel that exposes the prompt
 * sent to the AI grader and the raw JSON it returned, for a single
 * graded result. Two read-only `<pre>` blocks. Rendered inline when
 * the global "Show AI Reasoning" toggle is on.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX inside the
 * results map gated by `showAIReasoning`. Presentational only.
 *
 * Props:
 *   open: bool        — global "show AI reasoning" toggle
 *   aiInput: string   — the prompt the AI received (per-row)
 *   aiResponse: string — the raw AI response (per-row)
 */
import React from "react";

export default function AIReasoningPanel({ open, aiInput, aiResponse }) {
  if (!open) return null;

  const preStyle = {
    whiteSpace: "pre-wrap",
    wordWrap: "break-word",
    fontFamily: "monospace",
    fontSize: "0.8rem",
    lineHeight: "1.5",
    color: "var(--text-secondary)",
    background: "var(--glass-bg)",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid var(--glass-border)",
    maxHeight: "300px",
    overflowY: "auto",
    margin: 0,
  };

  return (
    <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "12px" }}>
      <div>
        <label className="label">Prompt Input (Sent to AI)</label>
        <pre style={preStyle}>{aiInput || "Not available"}</pre>
      </div>
      <div>
        <label className="label">Raw API Output (JSON)</label>
        <pre style={preStyle}>{aiResponse || "Not available"}</pre>
      </div>
    </div>
  );
}
