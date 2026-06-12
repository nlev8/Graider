import React from "react";
import { gradeColor } from "./gradeColor";

// Standards-coverage heatmap for the Compare Assessments tab (CQ wave-8
// split). Stateless; the remediation trigger state lives in the
// always-mounted shell and the setter is passed through with its original
// name so the red-cell click/keydown handlers stay byte-identical.
export default function StandardsHeatmap({ data, orderedSelected, setRemediationTrigger }) {
  if (data.standards_matrix.standards.length === 0) {
    return (
      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
        No standards-tagged questions on these assessments.
      </p>
    );
  }

  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "10px 14px", textAlign: "left", fontSize: "0.75rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)" }}>Standard</th>
            {orderedSelected.map(function(a) {
              return (
                <th key={a.content_id} style={{ padding: "10px 8px", fontSize: "0.7rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "100px", textAlign: "center" }}>
                  {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.standards_matrix.standards.map(function(code) {
            return (
              <tr key={code}>
                <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "8px 14px", fontFamily: "monospace", fontSize: "0.75rem", borderBottom: "1px solid var(--glass-border)" }}>{code}</td>
                {orderedSelected.map(function(a) {
                  var cell = (data.standards_matrix.cells[a.content_id] || {})[code];
                  var color = gradeColor(cell ? cell.percentage : null);
                  // Phase 4.2 #10: red cells (class mean < 70) become
                  // RemediationDrawer triggers in red_tier_in_class mode
                  // for that standard. UX copy in the tooltip clarifies
                  // that the remediation is class-wide-standard, NOT
                  // specific to this cell's content (Codex MAJOR — red
                  // tier resolves across all class content, not this cell).
                  var isRed = cell && typeof cell.percentage === "number" && cell.percentage < 70;
                  var cellTitle = isRed
                    ? "Class mean " + cell.percentage + "% on " + code + " (" + cell.students_assessed + " students). Click to generate a class-wide remediation for this standard."
                    : (cell ? code + " on " + a.title + ": " + cell.percentage + "% (" + cell.students_assessed + " students)" : "Not covered");
                  return (
                    <td key={a.content_id}
                        className={isRed ? "phase4-heatmap-red-clickable" : undefined}
                        title={cellTitle}
                        onClick={isRed ? function() {
                          setRemediationTrigger({ standardCode: code });
                        } : undefined}
                        onKeyDown={isRed ? function(e) {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setRemediationTrigger({ standardCode: code });
                          }
                        } : undefined}
                        role={isRed ? "button" : undefined}
                        tabIndex={isRed ? 0 : undefined}
                        style={{ padding: "8px", textAlign: "center", borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", background: color.bg, color: color.text, fontSize: "0.75rem", fontWeight: 600, cursor: isRed ? "pointer" : "default" }}>
                      {color.label}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
