import React from "react";
import { masteryColor } from "./helpers";

/**
 * CQ wave-8 split: the student × standard mastery grid (sticky student
 * column, red-tier header remediate CTAs, clickable mastery cells), moved
 * verbatim from ProgressRankGrid.jsx. Stateless — all state stays in the
 * shell; prop names match the shell's identifiers so the JSX body is a
 * pure move.
 */
export default function RankTable({
  standards, displayStudents, openReportCard, setSelectedCell, setRemediationTrigger,
}) {
  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "600px" }}>
        <thead>
          <tr>
            <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 2, padding: "10px 14px", textAlign: "left", fontSize: "0.8rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>
              Student
            </th>
            {/* Compute red counts per column once. */}
            {(function() {
              var redCounts = {};
              standards.forEach(function(code) {
                redCounts[code] = displayStudents.filter(function(stu) {
                  var m = stu.mastery[code];
                  return m && typeof m.percentage === "number" && m.percentage < 70;
                }).length;
              });
              return standards.map(function(code) {
                var redCount = redCounts[code];
                return (
                  <th key={code}
                      style={{ padding: "10px 8px", fontSize: "0.7rem", fontFamily: "monospace",
                               fontWeight: 700, borderBottom: "1px solid var(--glass-border)",
                               borderLeft: "1px solid var(--glass-border)", minWidth: "90px",
                               textAlign: "center", position: "relative" }}
                      className="phase4-header-cell">
                    {code}
                    {redCount > 0 && (
                      <button
                        onClick={function() {
                          setRemediationTrigger({
                            standardCode: code,
                            targetMode: "red_tier_in_class",
                          });
                        }}
                        className="phase4-header-remediate"
                        tabIndex={0}
                        aria-label={"Remediate " + redCount + " red-tier students on " + code}
                        style={{
                          position: "absolute", top: "2px", right: "2px",
                          background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                          border: "none", borderRadius: "4px", fontSize: "0.65rem",
                          padding: "2px 6px", cursor: "pointer", opacity: 0,
                          transition: "opacity 0.15s",
                        }}
                      >
                        Remediate ({redCount})
                      </button>
                    )}
                  </th>
                );
              });
            })()}
          </tr>
        </thead>
        <tbody>
          {displayStudents.map(function(student) {
            return (
              <tr key={student.student_id}>
                <td
                  onClick={function() { openReportCard(student); }}
                  style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)", cursor: "pointer" }}
                >
                  {student.student_name}
                </td>
                {standards.map(function(code) {
                  var m = student.mastery[code];
                  var color = masteryColor(m ? m.percentage : null);
                  var clickable = !!m;
                  function activate() {
                    if (clickable) setSelectedCell({ student: student, standard: code, mastery: m });
                  }
                  return (
                    <td
                      key={code}
                      onClick={activate}
                      onKeyDown={function(e) {
                        if (clickable && (e.key === "Enter" || e.key === " ")) {
                          e.preventDefault();
                          activate();
                        }
                      }}
                      role={clickable ? "button" : undefined}
                      tabIndex={clickable ? 0 : undefined}
                      aria-label={clickable
                        ? "View " + student.student_name + " " + code + " mastery (" + (m ? m.percentage : "no data") + "%)"
                        : undefined}
                      style={{
                        padding: "10px 8px",
                        textAlign: "center",
                        borderBottom: "1px solid var(--glass-border)",
                        borderLeft: "1px solid var(--glass-border)",
                        background: color.bg,
                        color: color.text,
                        fontSize: "0.8rem",
                        fontWeight: 600,
                        cursor: clickable ? "pointer" : "default",
                      }}
                      title={clickable ? "Click to see contributing submissions" : "No data"}
                    >
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
