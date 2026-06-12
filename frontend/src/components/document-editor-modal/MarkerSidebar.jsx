import React from "react";
import MarkedSectionsList from "./MarkedSectionsList";
import ExcludedSectionsPanel from "./ExcludedSectionsPanel";

export default function MarkerSidebar(props) {
  const { HIGHLIGHT_COLORS, addToast, applyAllHighlights, assignment, docEditorModal, importedDoc, removeAllHighlightsFromHtml, setAssignment, setDocEditorModal, setImportedDoc } = props;
  return (
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
              <MarkedSectionsList {...props} />

              {/* Excluded Sections */}
              <ExcludedSectionsPanel {...props} />

            </div>
  );
}
