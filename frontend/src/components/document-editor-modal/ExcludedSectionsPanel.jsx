import React from "react";
import Icon from "../Icon";

export default function ExcludedSectionsPanel({ HIGHLIGHT_COLORS, addToast, assignment, docEditorModal, setAssignment, setDocEditorModal }) {
  if (!((assignment.excludeMarkers || []).length > 0)) return null;
  return (
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
  );
}
