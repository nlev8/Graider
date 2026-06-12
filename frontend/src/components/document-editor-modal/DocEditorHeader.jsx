import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function DocEditorHeader({ HIGHLIGHT_COLORS, addSelectedAsMarker, assignment, docEditorModal, highlighterMode, importedDoc, setAssignment, setDocEditorModal, setHighlighterMode, setImportedDoc, setLoadedAssignmentName, setSavedAssignmentData, setSavedAssignments }) {
  return (
          <div
            style={{
              padding: "15px 25px",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "var(--modal-content-bg)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                <Icon name="FileEdit" size={20} />{" "}
                {importedDoc.filename || "Document Editor"}
              </h2>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {(assignment.customMarkers || []).length} markers selected
              </span>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => {
                  // Reset everything and close
                  setAssignment({
                    title: "",
                    subject: "Social Studies",
                    totalPoints: 100,
                    instructions: "",
                    questions: [],
                    customMarkers: [],
                    excludeMarkers: [],
                    gradingNotes: "",
                    responseSections: [],
                  });
                  setImportedDoc({
                    text: "",
                    html: "",
                    filename: "",
                    loading: false,
                  });
                  setLoadedAssignmentName("");
                  setDocEditorModal({ ...docEditorModal, show: false });
                }}
                className="btn btn-ghost"
                style={{ padding: "8px" }}
                title="Cancel and reset"
              >
                <Icon name="X" size={18} />
              </button>
              {/* Highlighter Mode Toggle */}
              <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                <button
                  onClick={() => setHighlighterMode("start")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "start" ? HIGHLIGHT_COLORS.start.bg : "transparent",
                    border: "none",
                    borderRight: "1px solid var(--glass-border)",
                    color: highlighterMode === "start" ? HIGHLIGHT_COLORS.start.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "start" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.start.border }} />
                  Start
                </button>
                <button
                  onClick={() => setHighlighterMode("end")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "end" ? HIGHLIGHT_COLORS.end.bg : "transparent",
                    border: "none",
                    borderRight: "1px solid var(--glass-border)",
                    color: highlighterMode === "end" ? HIGHLIGHT_COLORS.end.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "end" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.end.border }} />
                  End
                </button>
                <button
                  onClick={() => setHighlighterMode("exclude")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "exclude" ? HIGHLIGHT_COLORS.exclude.bg : "transparent",
                    border: "none",
                    color: highlighterMode === "exclude" ? HIGHLIGHT_COLORS.exclude.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "exclude" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.exclude.border }} />
                  Exclude
                </button>
              </div>
              <button
                onClick={addSelectedAsMarker}
                className="btn btn-secondary"
                style={{
                  background: HIGHLIGHT_COLORS[highlighterMode].bg,
                  borderColor: HIGHLIGHT_COLORS[highlighterMode].border,
                }}
              >
                <Icon name="Target" size={16} />
                Mark {HIGHLIGHT_COLORS[highlighterMode].label}
              </button>
              <button
                onClick={async () => {
                  // Save assignment if it has a title and markers
                  if (
                    assignment.title &&
                    (assignment.customMarkers || []).length > 0
                  ) {
                    try {
                      // Include highlighted HTML in the saved data
                      const docToSave = { ...importedDoc, html: docEditorModal.editedHtml };
                      const dataToSave = { ...assignment, importedDoc: docToSave };
                      await api.saveAssignmentConfig(dataToSave);
                      // Refresh saved assignments list
                      const list = await api.listAssignments();
                      if (list.assignments)
                        setSavedAssignments(list.assignments);
                      if (list.assignmentData)
                        setSavedAssignmentData(list.assignmentData);
                    } catch (error) {
                      console.error("Failed to save assignment:", error);
                    }
                  }
                  // Reset the form for a new assignment
                  setAssignment({
                    title: "",
                    subject: "Social Studies",
                    totalPoints: 100,
                    instructions: "",
                    questions: [],
                    customMarkers: [],
                    excludeMarkers: [],
                    gradingNotes: "",
                    responseSections: [],
                  });
                  setImportedDoc({
                    text: "",
                    html: "",
                    filename: "",
                    loading: false,
                  });
                  setLoadedAssignmentName("");
                  setDocEditorModal({ ...docEditorModal, show: false });
                }}
                className="btn btn-primary"
              >
                Done
              </button>
            </div>
          </div>
  );
}
