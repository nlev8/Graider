import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/*
 * Assignment Filter — relocated verbatim from GradeTab.jsx (CQ wave-2 split).
 * `{savedAssignments.length > 0 && (...)}` at the call site became the
 * early-return-null below.
 */
export default function AssignmentFilter({
  savedAssignments,
  savedAssignmentData,
  gradeFilterAssignment,
  setGradeFilterAssignment,
  setGradeAssignment,
  addToast,
}) {
  if (savedAssignments.length === 0) return null;
  return (
    <div
      data-tutorial="grade-assignment-filter"
      style={{
        padding: "15px",
        background:
          "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
        borderRadius: "12px",
        border: "1px solid rgba(16, 185, 129, 0.2)",
        marginBottom: "20px",
      }}
    >
      <label
        className="label"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <Icon
          name="FileText"
          size={16}
          style={{ color: "#10b981" }}
        />
        Filter by Assignment
      </label>
      <select
        className="input"
        value={gradeFilterAssignment}
        onChange={async (e) => {
          const assignmentName = e.target.value;
          setGradeFilterAssignment(assignmentName);
          // Auto-load the assignment config when selected
          if (assignmentName) {
            try {
              const data =
                await api.loadAssignment(assignmentName);
              if (data.assignment) {
                setGradeAssignment({
                  ...data.assignment,
                  title: data.assignment.title || "",
                  customMarkers:
                    data.assignment.customMarkers || [],
                  gradingNotes:
                    data.assignment.gradingNotes || "",
                  responseSections:
                    data.assignment.responseSections || [],
                  excludeMarkers:
                    data.assignment.excludeMarkers || [],
                });
                // PR 4: setGradeImportedDoc was removed — that App-level
                // state was dead (set but never read).
                addToast(
                  `Loaded "${assignmentName}"`,
                  "success",
                );
              }
            } catch (err) {
              console.error("Load error:", err);
            }
          }
        }}
        style={{ cursor: "pointer" }}
      >
        <option value="">Select Assignment...</option>
        {savedAssignments.map((name) => (
          <option key={name} value={name}>
            {name}
            {savedAssignmentData[name]?.completionOnly
              ? " (Completion)"
              : ""}
          </option>
        ))}
      </select>
      {gradeFilterAssignment && (
        <p
          style={{
            fontSize: "0.75rem",
            color: "#10b981",
            marginTop: "8px",
            fontWeight: 500,
          }}
        >
          ✓ Using "{gradeFilterAssignment}" configuration
        </p>
      )}
    </div>
  );
}
