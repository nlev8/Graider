import React from "react";
import Icon from "../../components/Icon";

/*
 * Suggested-markers library — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split).
 */
export default function MarkerLibrarySection({ assignment, setAssignment, config, markerLibrary }) {
  return (
    <div
      data-tutorial="builder-markers"
      style={{
        marginBottom: "25px",
        padding: "15px 20px",
        background: "rgba(99,102,241,0.1)",
        borderRadius: "12px",
        border: "1px solid rgba(99,102,241,0.2)",
      }}
    >
      <label
        style={{
          display: "block",
          fontSize: "0.9rem",
          fontWeight: 600,
          marginBottom: "10px",
        }}
      >
        <Icon
          name="Bookmark"
          size={16}
          style={{ marginRight: "8px" }}
        />
        Suggested Markers for{" "}
        {config.subject || "Social Studies"}
      </label>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        {(
          markerLibrary[config.subject] ||
          markerLibrary["Social Studies"] ||
          []
        ).map((marker, i) => (
          <span
            key={i}
            style={{
              padding: "6px 12px",
              background: "var(--btn-secondary-bg)",
              borderRadius: "6px",
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
            onClick={() => {
              // Check if marker already exists (handle both string and object formats)
              const exists = (assignment.customMarkers || []).some(m =>
                typeof m === 'string' ? m === marker : m.start === marker
              );
              if (!exists) {
                setAssignment({
                  ...assignment,
                  customMarkers: [
                    ...(assignment.customMarkers || []),
                    marker,
                  ],
                });
              }
            }}
            title="Click to add"
          >
            {typeof marker === 'string' ? marker : marker.start}
          </span>
        ))}
      </div>
    </div>
  );
}
