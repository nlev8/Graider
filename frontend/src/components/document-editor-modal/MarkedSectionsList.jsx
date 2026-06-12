import React from "react";
import Icon from "../Icon";

export default function MarkedSectionsList({ HIGHLIGHT_COLORS, addToast, assignment, docEditorModal, getEndMarker, getMarkerText, importedDoc, removeAllHighlightsFromHtml, removeMarker, setAssignment, setDocEditorModal, setImportedDoc }) {
  return (
    <>
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
    </>
  );
}
