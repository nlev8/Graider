import React from "react";
import Icon from "../Icon";
import ThemeToggle from "./ThemeToggle";
import { containerStyle, cardStyle, inputStyle, buttonStyle } from "./portalStyles";

// ============ NAME ENTRY SCREEN ============
// JSX moved verbatim from StudentPortal.jsx (CQ wave-6 split). Stage guard
// replaces the shell's original `if (stage === "name") return (...)` block.
export default function NameEntryScreen(props) {
  const {
    stage, lightMode, setLightMode,
    assessment, studentName, setStudentName, error, handleStartAssessment,
  } = props;
  if (stage !== "name") return null;

  return (
    <div style={containerStyle}>
      <ThemeToggle lightMode={lightMode} setLightMode={setLightMode} />
      <div style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div style={cardStyle}>
          <div style={{ textAlign: "center", marginBottom: "30px" }}>
            <Icon name="BookOpen" size={40} />
            <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
              {assessment?.title}
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              By {assessment?.teacher}
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: "20px", marginTop: "15px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
              {assessment?.total_points ? <span>{assessment.total_points} points</span> : null}
              {assessment?.total_points && assessment?.settings?.content_type !== 'assignment' && assessment?.time_estimate ? <span>{String.fromCharCode(8226)}</span> : null}
              {assessment?.settings?.content_type !== 'assignment' && assessment?.time_estimate ? <span>{assessment.time_estimate}</span> : null}
            </div>
          </div>

          {/* Restricted Assessment Notice */}
          {assessment?.settings?.is_makeup && (
            <div style={{ background: "var(--warning-bg)", border: "1px solid var(--warning-border)", borderRadius: "8px", padding: "12px 15px", marginBottom: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--warning)" }}>
                <Icon name="AlertCircle" size={18} />
                <strong>Makeup Exam</strong>
              </div>
              <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "5px" }}>
                This assessment is only available to specific students. Please enter your full name exactly as it appears on your roster.
              </p>
            </div>
          )}

          {assessment?.instructions && (
            <div style={{ background: "var(--glass-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", padding: "15px", marginBottom: "25px" }}>
              <strong>Instructions:</strong> {assessment.instructions}
            </div>
          )}

          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", marginBottom: "10px", fontWeight: 600 }}>
              <Icon name="User" size={16} /> Your Name
            </label>
            <input
              type="text"
              value={studentName}
              onChange={(e) => setStudentName(e.target.value)}
              placeholder="Enter your full name"
              style={{ ...inputStyle, textTransform: "none", textAlign: "left", letterSpacing: "normal" }}
              autoFocus
            />
          </div>

          {error && (
            <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", borderRadius: "8px", padding: "12px", marginBottom: "20px", color: "var(--danger-light)" }}>
              <Icon name="AlertCircle" size={16} /> {error}
            </div>
          )}

          <button onClick={handleStartAssessment} style={buttonStyle}>
            {(assessment?.settings?.content_type === 'assignment' || assessment?.type === 'assignment' || assessment?.type === 'project' || assessment?.type === 'essay') ? "Start Assignment" : "Start Assessment"} <Icon name="ArrowRight" />
          </button>
        </div>
      </div>
    </div>
  );
}
