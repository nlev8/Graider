import React from "react";
import Icon from "../../components/Icon";

/*
 * One saved-assignment card — relocated verbatim from the
 * `savedAssignments.map((name) => ...)` body in BuilderTab.jsx (CQ wave-9
 * split). The big inline onDoubleClick / star-toggle handlers moved to
 * createSavedAssignmentHandlers.js; the per-item `name` closure they relied
 * on is now passed as an argument at the call sites below.
 */
export default function SavedAssignmentItem({
  name,
  savedAssignmentData,
  loadedAssignmentName,
  loadAssignment,
  deleteAssignment,
  openSavedAssignment,
  toggleCountsTowardsGrade,
}) {
  const countsTowardsGrade = savedAssignmentData[name]?.countsTowardsGrade ?? true;
  return (
    <div
      style={{
        padding: "12px 15px",
        background:
          loadedAssignmentName === name
            ? "rgba(99,102,241,0.2)"
            : !countsTowardsGrade
              ? "rgba(100,100,100,0.1)"
              : "var(--input-bg)",
        borderRadius: "10px",
        border: !countsTowardsGrade
          ? "1px dashed rgba(100,100,100,0.4)"
          : "1px solid var(--glass-border)",
        outline: loadedAssignmentName === name
          ? "2px solid rgba(99,102,241,0.5)"
          : "none",
        outlineOffset: "-1px",
        cursor: "pointer",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        opacity: countsTowardsGrade ? 1 : 0.6,
      }}
      onClick={() => loadAssignment(name)}
      onDoubleClick={() => openSavedAssignment(name)}
      title="Double-click to open document with markers"
    >
      <div
        style={{
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "0.9rem",
          flex: 1,
        }}
      >
        <Icon
          name={
            savedAssignmentData[name]?.completionOnly
              ? "CheckCircle"
              : "FileText"
          }
          size={14}
          style={{
            color: savedAssignmentData[name]
              ?.completionOnly
              ? "#22c55e"
              : "#a5b4fc",
          }}
        />
        {name}
        {savedAssignmentData[name]?.completionOnly && (
          <span
            style={{
              fontSize: "0.7rem",
              background: "rgba(34, 197, 94, 0.2)",
              color: "#22c55e",
              padding: "2px 6px",
              borderRadius: "4px",
              marginLeft: "4px",
            }}
          >
            Completion
          </span>
        )}
        {savedAssignmentData[name]?.rubricType && savedAssignmentData[name]?.rubricType !== 'standard' && !savedAssignmentData[name]?.completionOnly && (
          <span
            style={{
              fontSize: "0.65rem",
              background: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "rgba(251, 191, 36, 0.2)" :
                         savedAssignmentData[name]?.rubricType === 'essay' ? "rgba(99, 102, 241, 0.2)" :
                         savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "rgba(34, 211, 238, 0.2)" :
                         savedAssignmentData[name]?.rubricType === 'custom' ? "rgba(139, 92, 246, 0.2)" : "rgba(100,100,100,0.2)",
              color: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "#fbbf24" :
                     savedAssignmentData[name]?.rubricType === 'essay' ? "#818cf8" :
                     savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "#22d3ee" :
                     savedAssignmentData[name]?.rubricType === 'custom' ? "#a78bfa" : "#888",
              padding: "2px 6px",
              borderRadius: "4px",
              marginLeft: "4px",
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            {savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? 'Fill-in' :
             savedAssignmentData[name]?.rubricType === 'cornell-notes' ? 'Cornell' :
             savedAssignmentData[name]?.rubricType}
          </span>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
        {/* Download button for generated worksheets */}
        {savedAssignmentData[name]?.worksheetDownloadUrl && (
          <a
            href={savedAssignmentData[name].worksheetDownloadUrl}
            download
            onClick={(e) => e.stopPropagation()}
            style={{
              padding: "4px",
              background: "none",
              border: "none",
              color: "#6366f1",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
            title="Download worksheet (.docx)"
          >
            <Icon name="Download" size={14} />
          </a>
        )}
        {/* Star toggle for "counts towards grade" */}
        <button
          onClick={(e) => toggleCountsTowardsGrade(name, e)}
          style={{
            padding: "4px",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: (savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "#fbbf24" : "var(--text-muted)",
          }}
          title={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Counts towards grade (click to exclude)" : "Excluded from grade (click to include)"}
        >
          <Icon name={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Star" : "StarOff"} size={14} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            deleteAssignment(name);
          }}
          style={{
            padding: "4px",
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
          }}
        >
          <Icon name="Trash2" size={14} />
        </button>
      </div>
    </div>
  );
}
