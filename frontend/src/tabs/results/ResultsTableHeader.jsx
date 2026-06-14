import React from "react";

/**
 * ResultsTableHeader — extracted from ResultsTable (CQ wave-3 split).
 * Renders the <thead> row with column labels and resize handles.
 * Pure move: no behavior change, all logic stays in the parent.
 */
export default function ResultsTableHeader({
  colWidths,
  defaultColPercents,
  handleResizeStart,
  theme,
}) {
  return (
    <>
      {colWidths && (
        <colgroup>
          {colWidths.map((w, i) => (
            <col key={i} style={{ width: w + "px" }} />
          ))}
        </colgroup>
      )}
      {!colWidths && (
        <colgroup>
          {defaultColPercents.map((p, i) => (
            <col key={i} style={{ width: p + "%" }} />
          ))}
        </colgroup>
      )}
      <thead>
        <tr>
          {["Student", "Assignment", "Time", "Score", "Grade", "Cost", "Authenticity", "Email", "Actions"].map((label, i) => (
            <th key={label} style={{ textAlign: i >= 3 ? "center" : undefined, position: "relative", overflow: "visible" }}>
              {label}
              {i < 8 && (
                <span
                  onMouseDown={(e) => handleResizeStart(e, i)}
                  style={{
                    position: "absolute",
                    right: -2,
                    top: 4,
                    bottom: 4,
                    width: "4px",
                    cursor: "col-resize",
                    borderRadius: "2px",
                    background: theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                    transition: "background 0.15s",
                    zIndex: 1,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-primary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"; }}
                />
              )}
            </th>
          ))}
        </tr>
      </thead>
    </>
  );
}
