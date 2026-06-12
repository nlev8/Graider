import React from "react";

// Timing — content-type aware: time limit + availability window for
// assessments, due date for assignments.
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split).
export default function TimingSection({ isAssessment, settings, setSettings }) {
  return (
    <div style={{ marginBottom: "25px" }}>
      <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
        {'Time Limit' + (isAssessment ? ' *' : ' (Optional)')}
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <input
          type="number"
          min="0"
          value={settings.timeLimit || ''}
          onChange={(e) => setSettings({ ...settings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
          placeholder={isAssessment ? "Required" : "No limit"}
          style={{
            width: "120px",
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.2)",
            background: "rgba(255,255,255,0.08)",
            color: "#e2e8f0",
            fontSize: "0.95rem",
          }}
        />
        <span style={{ color: "#94a3b8" }}>minutes</span>
      </div>
      {isAssessment ? (
        <div style={{ marginTop: "12px", display: "flex", gap: "10px" }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Available From</label>
            <input
              type="datetime-local"
              value={settings.availableFrom}
              onChange={(e) => setSettings({ ...settings, availableFrom: e.target.value })}
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "8px",
                border: "1px solid rgba(255,255,255,0.2)",
                background: "rgba(255,255,255,0.08)",
                color: "#e2e8f0",
                fontSize: "0.85rem",
              }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Available Until</label>
            <input
              type="datetime-local"
              value={settings.availableUntil}
              onChange={(e) => setSettings({ ...settings, availableUntil: e.target.value })}
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "8px",
                border: "1px solid rgba(255,255,255,0.2)",
                background: "rgba(255,255,255,0.08)",
                color: "#e2e8f0",
                fontSize: "0.85rem",
              }}
            />
          </div>
        </div>
      ) : (
        <div style={{ marginTop: "12px" }}>
          <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Due Date</label>
          <input
            type="datetime-local"
            value={settings.dueDate}
            onChange={(e) => setSettings({ ...settings, dueDate: e.target.value })}
            style={{
              width: "100%",
              maxWidth: "250px",
              padding: "8px 10px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(255,255,255,0.08)",
              color: "#e2e8f0",
              fontSize: "0.85rem",
            }}
          />
        </div>
      )}
    </div>
  );
}
