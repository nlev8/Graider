import React from "react";

// Assessment Category Toggle — assessments only.
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split). The
// shell's original `{isAssessment && (...)}` gate becomes the guard here.
export default function AssessmentCategoryToggle({ isAssessment, settings, setSettings }) {
  if (!isAssessment) return null;

  return (
    <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
      <button
        onClick={() => setSettings({...settings, assessmentCategory: 'formative'})}
        style={{
          flex: 1,
          padding: "10px 14px",
          borderRadius: "8px",
          border: settings.assessmentCategory === 'formative' ? "2px solid #22c55e" : "1px solid rgba(255,255,255,0.15)",
          background: settings.assessmentCategory === 'formative' ? "rgba(34, 197, 94, 0.15)" : "rgba(255,255,255,0.05)",
          color: settings.assessmentCategory === 'formative' ? "#86efac" : "#94a3b8",
          cursor: "pointer",
          textAlign: "left",
          transition: "all 0.2s",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Formative</div>
        <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>Quizzes, checks for understanding</div>
      </button>
      <button
        onClick={() => setSettings({...settings, assessmentCategory: 'summative'})}
        style={{
          flex: 1,
          padding: "10px 14px",
          borderRadius: "8px",
          border: settings.assessmentCategory === 'summative' ? "2px solid #ef4444" : "1px solid rgba(255,255,255,0.15)",
          background: settings.assessmentCategory === 'summative' ? "rgba(239, 68, 68, 0.15)" : "rgba(255,255,255,0.05)",
          color: settings.assessmentCategory === 'summative' ? "#fca5a5" : "#94a3b8",
          cursor: "pointer",
          textAlign: "left",
          transition: "all 0.2s",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Summative</div>
        <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>Unit tests, midterms, finals</div>
      </button>
    </div>
  );
}
