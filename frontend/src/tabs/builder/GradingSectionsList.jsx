import React from "react";
import Icon from "../../components/Icon";

/*
 * Grading Sections list (per-marker name/points/type rows + model-answer
 * previews + the always-present Effort row) — relocated verbatim from
 * BuilderTab.jsx (CQ wave-9 split). `{assignment.useSectionPoints && (...)}`
 * at the call site became the early-return-null below.
 */
export default function GradingSectionsList({
  assignment,
  setAssignment,
  removeMarker,
  getMarkerText,
  getMarkerPoints,
  getMarkerType,
}) {
  if (!assignment.useSectionPoints) return null;
  return (
    <div style={{ marginTop: "15px" }}>
      <div style={{ fontWeight: "600", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
        <Icon name="Target" size={16} />
        Grading Sections
      </div>
      {(assignment.customMarkers || []).length === 0 ? (
        <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "10px", background: "rgba(0,0,0,0.05)", borderRadius: "6px" }}>
          No sections defined. Select a template above or add sections manually.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {assignment.customMarkers.map((marker, i) => {
            const markerName = typeof marker === 'string' ? marker : marker.start;
            return (
            <React.Fragment key={i}>
            <div style={{
              display: "flex", alignItems: "center", gap: "8px", padding: "10px",
              background: "rgba(251,191,36,0.15)", borderRadius: "6px", border: "1px solid rgba(251,191,36,0.3)"
            }}>
              <Icon name="Target" size={14} style={{ color: "#f59e0b", flexShrink: 0 }} />
              <input
                type="text"
                value={getMarkerText(marker)}
                onChange={(e) => {
                  const updated = [...assignment.customMarkers];
                  if (typeof updated[i] === "string") {
                    updated[i] = { start: e.target.value, points: 10, type: "written" };
                  } else {
                    updated[i] = { ...updated[i], start: e.target.value };
                  }
                  setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                }}
                className="input"
                style={{ flex: 1, padding: "4px 8px", fontSize: "13px" }}
                placeholder="Section name..."
              />
              <input
                type="number"
                value={getMarkerPoints(marker)}
                onChange={(e) => {
                  const updated = [...assignment.customMarkers];
                  const pts = parseInt(e.target.value) || 0;
                  if (typeof updated[i] === "string") {
                    updated[i] = { start: updated[i], points: pts, type: "written" };
                  } else {
                    updated[i] = { ...updated[i], points: pts };
                  }
                  setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                }}
                style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                min="0"
                max="100"
              />
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
              <select
                value={getMarkerType(marker)}
                onChange={(e) => {
                  const updated = [...assignment.customMarkers];
                  if (typeof updated[i] === "string") {
                    updated[i] = { start: updated[i], points: 10, type: e.target.value };
                  } else {
                    updated[i] = { ...updated[i], type: e.target.value };
                  }
                  setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                }}
                style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", fontSize: "12px", background: "var(--input-bg)", color: "var(--text-primary)" }}
              >
                <option value="written">Written</option>
                <option value="short_answer">Short Answer</option>
                <option value="multiple_choice">Multiple Choice</option>
                <option value="fill-blank">Fill-blank</option>
                <option value="vocabulary">Vocabulary</option>
                <option value="matching">Matching</option>
                <option value="true_false">True/False</option>
                <option value="math_equation">Math Equation</option>
                <option value="data_table">Data Table</option>
              </select>
              <button
                onClick={() => removeMarker(marker, i)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: "4px", color: "#ef4444" }}
              >
                <Icon name="X" size={14} />
              </button>
            </div>
            {/* Model answer preview */}
            {assignment.modelAnswers && assignment.modelAnswers[markerName] && (
              <div style={{ marginLeft: "24px", marginBottom: "4px" }}>
                <label style={{ fontSize: "11px", color: "var(--text-secondary)", display: "block", marginBottom: "2px" }}>
                  Model Answer:
                </label>
                <textarea className="input"
                  value={assignment.modelAnswers[markerName]}
                  onChange={(e) => {
                    const updated = Object.assign({}, assignment.modelAnswers);
                    updated[markerName] = e.target.value;
                    setAssignment({ ...assignment, modelAnswers: updated });
                  }}
                  style={{ fontSize: "12px", minHeight: "60px", backgroundColor: "var(--bg-tertiary)", opacity: 0.9 }}
                />
              </div>
            )}
            </React.Fragment>
            );
          })}
          {/* Effort Points (always present) */}
          <div style={{
            display: "flex", alignItems: "center", gap: "8px", padding: "10px",
            background: "rgba(34,197,94,0.15)", borderRadius: "6px", border: "1px solid rgba(34,197,94,0.3)"
          }}>
            <Icon name="Star" size={14} style={{ color: "#22c55e", flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: "13px", fontWeight: "500" }}>Effort & Engagement</span>
            <input
              type="number"
              value={assignment.effortPoints || 15}
              onChange={(e) => setAssignment({ ...assignment, effortPoints: parseInt(e.target.value) || 0, sectionTemplate: "Custom" })}
              style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
              min="0"
              max="30"
            />
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
            <div style={{ width: "90px" }}></div> {/* Spacer to align with other rows */}
          </div>
        </div>
      )}
    </div>
  );
}
