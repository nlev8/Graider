import React from "react";
import Icon from "../Icon";

// Student Selection (only shown for makeup exams with a period selected).
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split). The
// shell's original `{settings.isMakeup && settings.periodFilename && (...)}`
// gate becomes the guard here — note this block is intentionally NOT gated
// on isAssessment (it renders whenever isMakeup + period, matching the
// original).
export default function StudentSelection({
  settings,
  setSettings,
  modalStudents,
  loadingStudents,
  studentAccommodations,
}) {
  if (!(settings.isMakeup && settings.periodFilename)) return null;

  return (
    <div style={{ marginBottom: "20px" }}>
      <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
        Select Students ({settings.selectedStudents.length} selected)
      </label>
      {loadingStudents ? (
        <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8" }}>
          <Icon name="Loader" size={24} className="spin" />
          <div style={{ marginTop: "10px" }}>Loading students...</div>
        </div>
      ) : modalStudents.length === 0 ? (
        <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8" }}>
          No students in this period
        </div>
      ) : (
        <div
          style={{
            maxHeight: "200px",
            overflowY: "auto",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: "8px",
            background: "rgba(255,255,255,0.05)",
          }}
        >
          {modalStudents.map((student, idx) => {
            const studentName = student.first + ' ' + student.last;
            const isSelected = settings.selectedStudents.includes(studentName);
            const studentId = student.id || student.email || studentName;
            const hasAccommodation = studentAccommodations[studentId];
            return (
              <label
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "10px 12px",
                  borderBottom: idx < modalStudents.length - 1 ? "1px solid rgba(255,255,255,0.15)" : "none",
                  cursor: "pointer",
                  background: isSelected ? "rgba(139, 92, 246, 0.1)" : "transparent",
                }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSettings({ ...settings, selectedStudents: [...settings.selectedStudents, studentName] });
                    } else {
                      setSettings({ ...settings, selectedStudents: settings.selectedStudents.filter(s => s !== studentName) });
                    }
                  }}
                  style={{ width: "16px", height: "16px", accentColor: "var(--accent-primary)" }}
                />
                <span style={{ flex: 1 }}>{studentName}</span>
                {hasAccommodation && (
                  <span
                    style={{
                      padding: "2px 8px",
                      background: "rgba(59, 130, 246, 0.2)",
                      color: "#3b82f6",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                    }}
                  >
                    IEP/504
                  </span>
                )}
              </label>
            );
          })}
        </div>
      )}
      {settings.isMakeup && modalStudents.length > 0 && (
        <div style={{ marginTop: "8px", display: "flex", gap: "10px" }}>
          <button
            onClick={() => setSettings({ ...settings, selectedStudents: modalStudents.map(s => s.first + ' ' + s.last) })}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
          >
            Select All
          </button>
          <button
            onClick={() => setSettings({ ...settings, selectedStudents: [] })}
            className="btn btn-secondary"
            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}
