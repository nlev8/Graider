import React from "react";

// Makeup Exam Toggle — assessments only.
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split). The
// shell's original `{isAssessment && (...)}` gate becomes the guard here.
export default function MakeupToggle({ isAssessment, settings, setSettings }) {
  if (!isAssessment) return null;

  return (
    <div style={{ marginBottom: "20px" }}>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          cursor: "pointer",
          padding: "12px 15px",
          background: settings.isMakeup ? "rgba(139, 92, 246, 0.1)" : "rgba(255,255,255,0.05)",
          border: settings.isMakeup ? "1px solid #8b5cf6" : "1px solid rgba(255,255,255,0.15)",
          borderRadius: "8px",
        }}
      >
        <input
          type="checkbox"
          checked={settings.isMakeup}
          onChange={(e) => setSettings({ ...settings, isMakeup: e.target.checked, selectedStudents: [] })}
          style={{ width: "18px", height: "18px", accentColor: "var(--accent-primary)" }}
        />
        <div>
          <div style={{ fontWeight: 600 }}>Makeup Exam</div>
          <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
            Restrict to selected students only
          </div>
        </div>
      </label>
    </div>
  );
}
