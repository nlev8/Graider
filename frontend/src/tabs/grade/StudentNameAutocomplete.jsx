import React from "react";
import Icon from "../../components/Icon";

/*
 * Student-name input with roster autocomplete for the Individual Upload panel.
 * Relocated verbatim from GradeTab.jsx (CQ wave-2 split).
 */
export default function StudentNameAutocomplete({
  individualUpload,
  setIndividualUpload,
  periodStudents,
  getStudentSuggestions,
}) {
  return (
    <div style={{ position: "relative" }}>
      <input
        type="text"
        className="input"
        placeholder={
          periodStudents.length > 0
            ? "Start typing student name..."
            : "Student name..."
        }
        value={individualUpload.studentName}
        onChange={(e) =>
          setIndividualUpload((prev) => ({
            ...prev,
            studentName: e.target.value,
            studentInfo: null, // Clear selected student when typing
            showSuggestions: e.target.value.length >= 2,
          }))
        }
        onFocus={() =>
          setIndividualUpload((prev) => ({
            ...prev,
            showSuggestions: prev.studentName.length >= 2,
          }))
        }
        onBlur={() =>
          setTimeout(
            () =>
              setIndividualUpload((prev) => ({
                ...prev,
                showSuggestions: false,
              })),
            200,
          )
        }
      />
      {/* Autocomplete Dropdown */}
      {individualUpload.showSuggestions &&
        getStudentSuggestions(
          individualUpload.studentName,
        ).length > 0 && (
          <div
            style={{
              position: "absolute",
              top: "100%",
              left: 0,
              right: 0,
              background: "var(--card-bg)",
              border: "1px solid var(--glass-border)",
              borderRadius: "8px",
              marginTop: "4px",
              zIndex: 100,
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              maxHeight: "200px",
              overflowY: "auto",
            }}
          >
            {getStudentSuggestions(
              individualUpload.studentName,
            ).map((student, idx) => (
              <div
                key={idx}
                onClick={() =>
                  setIndividualUpload((prev) => ({
                    ...prev,
                    studentName:
                      student.full ||
                      `${student.first} ${student.last}`,
                    studentInfo: student,
                    showSuggestions: false,
                  }))
                }
                style={{
                  padding: "10px 12px",
                  cursor: "pointer",
                  borderBottom:
                    idx <
                    getStudentSuggestions(
                      individualUpload.studentName,
                    ).length -
                      1
                      ? "1px solid var(--glass-border)"
                      : "none",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
                onMouseEnter={(e) =>
                  (e.target.style.background =
                    "var(--glass-bg)")
                }
                onMouseLeave={(e) =>
                  (e.target.style.background =
                    "transparent")
                }
              >
                <Icon
                  name="User"
                  size={16}
                  style={{ color: "var(--text-muted)" }}
                />
                <div>
                  <div style={{ fontWeight: 500 }}>
                    {student.full ||
                      `${student.first} ${student.last}`}
                  </div>
                  {student.email && (
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      {student.email}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      {/* Selected Student Indicator */}
      {individualUpload.studentInfo && (
        <div
          style={{
            marginTop: "6px",
            fontSize: "0.75rem",
            color: "#10b981",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <Icon name="CheckCircle" size={12} />
          Student matched from roster
        </div>
      )}
    </div>
  );
}
