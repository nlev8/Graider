import React from "react";
import Icon from "../../components/Icon";
import SavedAssignmentItem from "./SavedAssignmentItem";

/*
 * Saved Assignments collapsible card — relocated verbatim from
 * BuilderTab.jsx (CQ wave-9 split). savedAssignmentsExpanded stays
 * BuilderTab-owned state (threaded as props) so expand/collapse survives
 * any remount of this card — identical lifecycle to the pre-split inline
 * JSX. The per-name map body lives in SavedAssignmentItem.jsx (key moved
 * from the item's root div to the map call site).
 */
export default function SavedAssignmentsCard({
  savedAssignments,
  savedAssignmentData,
  loadedAssignmentName,
  savedAssignmentsExpanded,
  setSavedAssignmentsExpanded,
  loadAssignment,
  deleteAssignment,
  openSavedAssignment,
  toggleCountsTowardsGrade,
}) {
  return (
    <div
      data-tutorial="builder-saved"
      className="glass-card"
      style={{ padding: "15px 20px", marginBottom: "20px" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
        onClick={() =>
          setSavedAssignmentsExpanded(!savedAssignmentsExpanded)
        }
      >
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "10px",
            margin: 0,
          }}
        >
          <Icon
            name={
              savedAssignmentsExpanded
                ? "ChevronDown"
                : "ChevronRight"
            }
            size={18}
            style={{ color: "var(--text-secondary)" }}
          />
          <Icon
            name="FolderOpen"
            size={18}
            style={{ color: "#10b981" }}
          />
          Saved Assignments ({savedAssignments.length})
        </h3>
      </div>

      {savedAssignmentsExpanded && (
        <>
          {savedAssignments.length === 0 ? (
            <p
              style={{
                textAlign: "center",
                padding: "20px",
                color: "var(--text-muted)",
                margin: 0,
              }}
            >
              No saved assignments yet. Create one below!
            </p>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "repeat(auto-fill, minmax(250px, 1fr))",
                gap: "10px",
                marginTop: "15px",
              }}
            >
              {savedAssignments.map((name) => (
                <SavedAssignmentItem
                  key={name}
                  name={name}
                  savedAssignmentData={savedAssignmentData}
                  loadedAssignmentName={loadedAssignmentName}
                  loadAssignment={loadAssignment}
                  deleteAssignment={deleteAssignment}
                  openSavedAssignment={openSavedAssignment}
                  toggleCountsTowardsGrade={toggleCountsTowardsGrade}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
