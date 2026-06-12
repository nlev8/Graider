import React from "react";
import Icon from "../../components/Icon";

/*
 * Point Distribution summary — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split). `{assignment.useSectionPoints && (...)}` at the call
 * site became the early-return-null below.
 */
export default function SectionPointSummary({ assignment, setAssignment, calculateTotalPoints }) {
  if (!assignment.useSectionPoints) return null;
  return (
    <div style={{ marginBottom: "20px", padding: "15px", background: "rgba(59,130,246,0.05)", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.15)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="Calculator" size={16} style={{ color: "#3b82f6" }} />
          <span style={{ fontWeight: "500", fontSize: "14px" }}>Point Distribution</span>
        </div>
        <button
          onClick={() => {
            // Redistribute points evenly among existing markers
            const markers = assignment.customMarkers || [];
            if (markers.length === 0) return;
            const effortPts = assignment.effortPoints || 15;
            const availablePoints = 100 - effortPts;
            const pointsPerMarker = Math.floor(availablePoints / markers.length);
            const remainder = availablePoints % markers.length;
            const redistributed = markers.map((m, i) => ({
              ...m,
              start: typeof m === 'string' ? m : m.start,
              points: pointsPerMarker + (i === 0 ? remainder : 0),
            }));
            setAssignment({ ...assignment, customMarkers: redistributed });
          }}
          className="btn btn-secondary"
          style={{ fontSize: "12px", padding: "4px 10px" }}
        >
          Distribute Evenly
        </button>
      </div>
      <div style={{ padding: "8px", background: "rgba(0,0,0,0.1)", borderRadius: "4px", fontSize: "13px" }}>
        <strong>Total Points:</strong> {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15)}
        {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15) !== 100 && (
          <span style={{ color: "#ef4444", marginLeft: "10px" }}>
            (Should equal 100)
          </span>
        )}
      </div>
    </div>
  );
}
