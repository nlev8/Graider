import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function DocumentEditorModal({ HIGHLIGHT_COLORS, addSelectedAsMarker, addToast, applyAllHighlights, assignment, docEditorModal, docHtmlRef, getEndMarker, getMarkerText, highlighterMode, importedDoc, removeAllHighlightsFromHtml, removeMarker, setAssignment, setDocEditorModal, setHighlighterMode, setImportedDoc, setLoadedAssignmentName, setSavedAssignmentData, setSavedAssignments }) {
  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
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
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: "1fr 300px",
              overflow: "hidden",
            }}
          >
            <div style={{ overflow: "auto", padding: "20px" }}>
              <iframe
                ref={docHtmlRef}
                srcDoc={`<!DOCTYPE html><html><head><style>body{font-family:Georgia,serif;padding:40px;background:#fff;color:#000;line-height:1.6}::selection{background:#6366f1;color:#fff}</style></head><body>${docEditorModal.editedHtml}</body></html>`}
                style={{
                  width: "100%",
                  height: "100%",
                  border: "none",
                  borderRadius: "8px",
                  minHeight: "600px",
                }}
              />
            </div>
            <div
              style={{
                borderLeft: "1px solid var(--glass-border)",
                padding: "20px",
                overflowY: "auto",
                background: "var(--sidebar-bg)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                <h3 style={{ fontSize: "1rem", margin: 0 }}>
                  Marked Sections ({(assignment.customMarkers || []).length})
                </h3>
                {(assignment.customMarkers || []).length > 0 && (
                  <button
                    onClick={() => {
                      if (!confirm("Remove all markers and highlights?")) return;
                      let cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);
                      // Re-apply exclude marker highlights (preserve orange)
                      cleanHtml = applyAllHighlights(cleanHtml, [], assignment.excludeMarkers);
                      setAssignment({ ...assignment, customMarkers: [] });
                      setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                      setImportedDoc({ ...importedDoc, html: cleanHtml });
                      addToast("All markers cleared", "success");
                    }}
                    style={{
                      background: "none",
                      border: "1px solid rgba(239,68,68,0.3)",
                      color: "#ef4444",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                    }}
                  >
                    Clear All
                  </button>
                )}
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Select text and use <span style={{color: HIGHLIGHT_COLORS.start.border, fontWeight: 600}}>Start</span> (green) to mark section beginnings, <span style={{color: HIGHLIGHT_COLORS.end.border, fontWeight: 600}}>End</span> (red) to mark where they stop
              </p>
              {(assignment.customMarkers || []).length === 0 ? (
                <div>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "10px" }}>
                    No markers yet
                  </p>
                  {docEditorModal.editedHtml && docEditorModal.editedHtml.includes('data-marker-id=') && (
                    <button
                      onClick={() => {
                        const cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);
                        setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                        setImportedDoc({ ...importedDoc, html: cleanHtml });
                        addToast("Orphaned highlights removed", "success");
                      }}
                      className="btn btn-secondary"
                      style={{
                        fontSize: "0.8rem",
                        padding: "6px 12px",
                        background: "rgba(239,68,68,0.15)",
                        border: "1px solid rgba(239,68,68,0.3)",
                        color: "#ef4444",
                      }}
                    >
                      <Icon name="Trash2" size={14} />
                      Remove Orphaned Highlights
                    </button>
                  )}
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  {(assignment.customMarkers || []).map((marker, i) => {
                    const markerName = typeof marker === 'string' ? marker : marker.start;
                    return (
                    <React.Fragment key={i}>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                        padding: "8px 12px",
                        background: "rgba(251,191,36,0.2)",
                        borderRadius: "6px",
                        border: "1px solid rgba(251,191,36,0.3)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon
                          name="Target"
                          size={12}
                          style={{ color: "#22c55e", flexShrink: 0 }}
                        />
                        <span
                          style={{
                            fontSize: "0.8rem",
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {getMarkerText(marker).substring(0, 60)}{getMarkerText(marker).length > 60 ? '...' : ''}
                        </span>
                        <button
                          onClick={() => removeMarker(marker, i)}
                          style={{
                            background: "none",
                            border: "none",
                            color: "var(--text-muted)",
                            cursor: "pointer",
                            padding: "0",
                          }}
                        >
                          <Icon name="X" size={12} />
                        </button>
                      </div>
                      {/* End marker display */}
                      {getEndMarker(marker) && (
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "20px" }}>
                          <Icon name="Flag" size={10} style={{ color: HIGHLIGHT_COLORS.end.border, flexShrink: 0 }} />
                          <span style={{ fontSize: "0.75rem", color: HIGHLIGHT_COLORS.end.border }}>
                            End: {getEndMarker(marker).substring(0, 40)}{getEndMarker(marker).length > 40 ? '...' : ''}
                          </span>
                        </div>
                      )}
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
                </div>
              )}

              {/* Excluded Sections */}
              {(assignment.excludeMarkers || []).length > 0 && (
                <div style={{ marginTop: "20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <h3 style={{ fontSize: "0.95rem", margin: 0, color: HIGHLIGHT_COLORS.exclude.border }}>
                      <Icon name="EyeOff" size={14} style={{ marginRight: "6px" }} />
                      Excluded Sections ({(assignment.excludeMarkers || []).length})
                    </h3>
                    <button
                      onClick={() => {
                        if (!confirm("Remove all exclude markers?")) return;
                        // Remove all exclude highlights from HTML (handles nested -line/-seg sub-IDs)
                        let cleanHtml = docEditorModal.editedHtml;
                        while (cleanHtml.includes('data-marker-id="exclude-')) {
                          cleanHtml = cleanHtml.replace(/<span[^>]*data-marker-id="exclude-[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
                        }
                        setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                        setAssignment({ ...assignment, excludeMarkers: [] });
                        addToast("All exclude markers cleared", "info");
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        fontSize: "0.75rem",
                      }}
                    >
                      Clear all
                    </button>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    {(assignment.excludeMarkers || []).map((marker, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          padding: "8px 12px",
                          background: HIGHLIGHT_COLORS.exclude.bg,
                          borderRadius: "6px",
                          border: `1px solid ${HIGHLIGHT_COLORS.exclude.border}`,
                        }}
                      >
                        <Icon
                          name="EyeOff"
                          size={12}
                          style={{ color: HIGHLIGHT_COLORS.exclude.border, flexShrink: 0 }}
                        />
                        <span
                          style={{
                            fontSize: "0.8rem",
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            color: HIGHLIGHT_COLORS.exclude.border,
                          }}
                        >
                          {marker.substring(0, 60)}{marker.length > 60 ? '...' : ''}
                        </span>
                        <button
                          onClick={() => {
                            // Remove this exclude marker
                            const newExcludeMarkers = [...(assignment.excludeMarkers || [])];
                            newExcludeMarkers.splice(i, 1);
                            // Remove highlight from HTML (handles nested -line/-seg sub-IDs)
                            const regex = new RegExp(`<span[^>]*data-marker-id="exclude-${i}(?:-[^"]*)?\"[^>]*>(.*?)<\\/span>`, 'gis');
                            let cleanHtml = docEditorModal.editedHtml;
                            // Run repeatedly to handle nested spans from multi-line/segment highlights
                            while (regex.test(cleanHtml)) {
                              regex.lastIndex = 0;
                              cleanHtml = cleanHtml.replace(regex, '$1');
                            }
                            setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                            setAssignment({ ...assignment, excludeMarkers: newExcludeMarkers });
                            addToast("Exclude marker removed", "info");
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            color: "var(--text-muted)",
                            cursor: "pointer",
                            padding: "0",
                          }}
                        >
                          <Icon name="X" size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "8px", fontStyle: "italic" }}>
                    These sections will NOT be graded or penalized.
                  </p>
                </div>
              )}

            </div>
          </div>
        </div>
  );
}
