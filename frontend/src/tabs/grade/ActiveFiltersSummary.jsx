import React from "react";
import Icon from "../../components/Icon";

/*
 * Active Filters Summary — relocated verbatim from GradeTab.jsx (CQ wave-2
 * split). `{(gradeFilterStudent || gradeFilterAssignment) && (...)}` at the
 * call site became the early-return-null below.
 */
export default function ActiveFiltersSummary({
  gradeFilterStudent,
  gradeFilterAssignment,
  setGradeFilterStudent,
  setGradeFilterAssignment,
}) {
  if (!gradeFilterStudent && !gradeFilterAssignment) return null;
  return (
    <div
      style={{
        padding: "12px 15px",
        background: "rgba(251, 191, 36, 0.1)",
        borderRadius: "10px",
        border: "1px solid rgba(251, 191, 36, 0.3)",
        marginBottom: "20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "10px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        <Icon
          name="Filter"
          size={16}
          style={{ color: "#f59e0b" }}
        />
        <span
          style={{
            fontSize: "0.85rem",
            color: "#f59e0b",
            fontWeight: 600,
          }}
        >
          Active Filters:
        </span>
        {gradeFilterStudent && (
          <span
            style={{
              padding: "4px 10px",
              background: "rgba(99, 102, 241, 0.2)",
              borderRadius: "6px",
              fontSize: "0.8rem",
              color: "var(--accent-primary)",
            }}
          >
            Student: {gradeFilterStudent}
          </span>
        )}
        {gradeFilterAssignment && (
          <span
            style={{
              padding: "4px 10px",
              background: "rgba(16, 185, 129, 0.2)",
              borderRadius: "6px",
              fontSize: "0.8rem",
              color: "#10b981",
            }}
          >
            Assignment: {gradeFilterAssignment}
          </span>
        )}
      </div>
      <button
        onClick={() => {
          setGradeFilterStudent("");
          setGradeFilterAssignment("");
        }}
        style={{
          padding: "4px 10px",
          background: "rgba(239, 68, 68, 0.1)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "6px",
          color: "#ef4444",
          fontSize: "0.8rem",
          cursor: "pointer",
        }}
      >
        Clear Filters
      </button>
    </div>
  );
}
