import React from "react";
import { gradeColor } from "./gradeColor";
import BoxPlotRow from "./BoxPlotRow";
import StandardsHeatmap from "./StandardsHeatmap";

// Comparison output (stat cards + box plot + standards heatmap) for the
// Compare Assessments tab (CQ wave-8 split). Stateless; rendered by the
// shell only in the `data` branch of its loading/error/data ternary, so the
// pre-split IIFE wrapper became a plain function body here.
export default function ComparisonResults({ data, orderedSelected, setRemediationTrigger }) {
  // O(1) lookup of full assessment-shape object by content_id.
  // Backend always returns one entry per requested content_id, but
  // filter just in case to avoid feeding gradebook-shape objects
  // (which lack distribution stats) into BoxPlotRow.
  var byId = new Map(data.assessments.map(function(a) { return [a.content_id, a]; }));
  var orderedFull = orderedSelected.map(function(o) { return byId.get(o.content_id); }).filter(Boolean);
  return (
    <div>
      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px", marginBottom: "20px" }}>
        {data.assessments.map(function(a) {
          var color = gradeColor(a.n > 0 ? a.mean : null);
          var ratePct = Math.round((a.submission_rate || 0) * 100);
          return (
            <div key={a.content_id} style={{ padding: "12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: color.bg }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: color.text, marginBottom: "4px" }}>{a.title}</div>
              {a.n > 0 ? (
                <div style={{ fontSize: "1.4rem", fontWeight: 700, color: color.text }}>
                  {a.mean}%
                </div>
              ) : (
                <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-muted)" }}>
                  No submissions yet
                </div>
              )}
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                {a.n} of {data.class_roster_size} {String.fromCharCode(8226)} {ratePct}% submitted
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Max points: {a.max_points}
                {a.n > 0 ? " " + String.fromCharCode(8226) + " median " + a.median + "%" : ""}
              </div>
            </div>
          );
        })}
      </div>

      {/* Box plot row */}
      <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Score distribution</h4>
      <div style={{ overflowX: "auto", marginBottom: "20px", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "8px" }}>
        <BoxPlotRow assessments={orderedFull} />
      </div>

      {/* Standards heatmap */}
      <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Standards coverage</h4>
      <StandardsHeatmap data={data} orderedSelected={orderedSelected} setRemediationTrigger={setRemediationTrigger} />
    </div>
  );
}
