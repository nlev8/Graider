import React from "react";
import Icon from "../../components/Icon";
import SectionPointSummary from "./SectionPointSummary";
import ManualMarkerInput from "./ManualMarkerInput";
import GradingSectionsList from "./GradingSectionsList";

/*
 * Import Document & Mark Sections panel — relocated verbatim from
 * BuilderTab.jsx (CQ wave-9 split). The panel's inner blocks (point
 * summary, manual marker input, grading sections list) live in their own
 * sibling components; their `useSectionPoints` guards moved with them as
 * early-return-nulls.
 */
export default function ImportDocumentSection({
  assignment,
  setAssignment,
  importedDoc,
  setImportedDoc,
  setLoadedAssignmentName,
  fileInputRef,
  handleDocImport,
  openDocEditor,
  removeMarker,
  getMarkerText,
  getMarkerPoints,
  getMarkerType,
  calculateTotalPoints,
}) {
  return (
    <div
      data-tutorial="builder-import"
      style={{
        marginBottom: "25px",
        padding: "20px",
        background: "rgba(251,191,36,0.1)",
        borderRadius: "12px",
        border: "1px solid rgba(251,191,36,0.3)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h3
            style={{
              fontSize: "1rem",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "5px",
            }}
          >
            <Icon name="FileUp" size={20} />
            Import Document & Mark Sections
          </h3>
          <p
            style={{
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              margin: 0,
            }}
          >
            {importedDoc.text ? (
              <>
                <strong style={{ color: "#fbbf24" }}>
                  {importedDoc.filename}
                </strong>{" "}
                loaded
              </>
            ) : (
              "Import a Word or PDF to highlight gradeable sections"
            )}
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleDocImport}
            accept=".docx,.pdf,.doc,.txt"
            style={{ display: "none" }}
          />
          {importedDoc.text && (
            <>
              <button
                onClick={openDocEditor}
                className="btn btn-secondary"
              >
                <Icon name="Edit" size={16} />
                Edit & Mark
              </button>
              <button
                onClick={() => {
                  setImportedDoc({
                    text: "",
                    html: "",
                    filename: "",
                    loading: false,
                  });
                  setAssignment({
                    ...assignment,
                    title: "",
                    customMarkers: [],
                  });
                  setLoadedAssignmentName("");
                }}
                className="btn btn-secondary"
                style={{
                  background: "rgba(239,68,68,0.2)",
                  color: "#ef4444",
                }}
                title="Clear imported document"
              >
                <Icon name="Trash2" size={16} />
              </button>
            </>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="btn btn-primary"
            style={{
              background:
                "linear-gradient(135deg, #f59e0b, #d97706)",
            }}
          >
            <Icon name="Upload" size={16} />
            {importedDoc.loading
              ? "Loading..."
              : "Import Word/PDF"}
          </button>
        </div>
      </div>

      {/* Section Point Values Toggle */}
      <div style={{ marginTop: "20px", marginBottom: "15px", padding: "15px", background: "rgba(59,130,246,0.1)", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.2)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="Sliders" size={18} style={{ color: "#3b82f6" }} />
            <span style={{ fontWeight: "600" }}>Use Section Point Values</span>
          </div>
          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={assignment.useSectionPoints || false}
              onChange={(e) => {
                const enabled = e.target.checked;
                if (enabled) {
                  // When enabling, add point values to existing markers (distribute evenly)
                  const existingMarkers = assignment.customMarkers || [];
                  const effortPts = assignment.effortPoints ?? 15;
                  let markersWithPoints;

                  if (existingMarkers.length > 0) {
                    // Distribute remaining points evenly among existing markers
                    const availablePoints = 100 - effortPts;
                    const pointsPerMarker = Math.floor(availablePoints / existingMarkers.length);
                    const remainder = availablePoints % existingMarkers.length;

                    markersWithPoints = existingMarkers.map((m, i) => {
                      const markerText = typeof m === 'string' ? m : m.start;
                      const markerType = typeof m === 'object' ? (m.type || 'written') : 'written';
                      const pts = pointsPerMarker + (i === 0 ? remainder : 0);
                      return { start: markerText, points: pts, type: markerType };
                    });
                  } else {
                    // No markers - create a default Content section
                    markersWithPoints = [{ start: "Content", points: 100 - effortPts, type: "written" }];
                  }

                  setAssignment({
                    ...assignment,
                    useSectionPoints: true,
                    customMarkers: markersWithPoints,
                    effortPoints: effortPts,
                    sectionTemplate: "Custom",
                  });
                } else {
                  setAssignment({ ...assignment, useSectionPoints: false });
                }
              }}
              style={{ width: "18px", height: "18px", cursor: "pointer" }}
            />
          </label>
        </div>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "8px" }}>
          {assignment.useSectionPoints
            ? "Grade each section with specific point values"
            : "Use standard rubric (Content 40, Completeness 25, Writing 20, Effort 15)"}
        </div>
      </div>

      {/* Section Point Summary - Only show when toggle is ON */}
      <SectionPointSummary
        assignment={assignment}
        setAssignment={setAssignment}
        calculateTotalPoints={calculateTotalPoints}
      />

      {/* Manual Marker Input */}
      <ManualMarkerInput assignment={assignment} setAssignment={setAssignment} />

      {/* Grading Sections with Points - Only show when toggle is ON */}
      <GradingSectionsList
        assignment={assignment}
        setAssignment={setAssignment}
        removeMarker={removeMarker}
        getMarkerText={getMarkerText}
        getMarkerPoints={getMarkerPoints}
        getMarkerType={getMarkerType}
      />
    </div>
  );
}
