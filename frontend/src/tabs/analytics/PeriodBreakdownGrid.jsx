import React from "react";
import Icon from "../../components/Icon";

/**
 * PeriodBreakdownGrid — pure-prop per-period breakdown for PeriodMissingReport.
 * Extracted from PeriodMissingReport (CQ wave cq8-04 split).
 *
 * Renders the collapsible per-period student list grid.
 * No state, effects, or fetches — all values and handlers are props.
 */
export default function PeriodBreakdownGrid({
  periodReports,
  assignmentViewMode,
  missingPeriodFilter,
  expandedPeriods,
  setExpandedPeriods,
}) {
  return (
    <div style={{ display: "grid", gap: "12px" }}>
      {periodReports.map((report) => {
        const canCollapse = !missingPeriodFilter && periodReports.length > 1;
        const isCollapsed = canCollapse && !expandedPeriods.has(report.period);
        const displayStudents = assignmentViewMode === "submitted"
          ? report.studentsWithSubmitted
          : report.studentsWithMissing;
        const isMissing = assignmentViewMode === "missing";
        return (
          <div
            key={report.period}
            style={{
              padding: "12px 15px",
              background: "rgba(0,0,0,0.15)",
              borderRadius: "8px",
              border: isMissing
                ? (report.allComplete ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(251,191,36,0.3)")
                : "1px solid rgba(16,185,129,0.3)",
            }}
          >
            <div
              onClick={canCollapse ? () => {
                setExpandedPeriods(prev => {
                  const next = new Set(prev);
                  if (next.has(report.period)) next.delete(report.period);
                  else next.add(report.period);
                  return next;
                });
              } : undefined}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: canCollapse ? "pointer" : "default",
                marginBottom:
                  !isCollapsed && displayStudents.length > 0
                    ? "10px"
                    : 0,
              }}
            >
              <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                {canCollapse && (
                  <Icon name={isCollapsed ? "ChevronRight" : "ChevronDown"} size={16} style={{ opacity: 0.6 }} />
                )}
                {report.period}
              </span>
              <span style={{ fontSize: "0.85rem" }}>
                {isMissing ? (
                  report.allComplete ? (
                    <span style={{ color: "#10b981" }}>
                      ✓ All complete
                    </span>
                  ) : (
                    <span style={{ color: "#b45309" }}>
                      {report.studentsWithMissing.length}{" "}
                      students missing work
                    </span>
                  )
                ) : (
                  <span style={{ color: "#059669" }}>
                    {report.studentsWithSubmitted.length} students with submissions
                  </span>
                )}
              </span>
            </div>
            {!isCollapsed && displayStudents.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                {displayStudents.map(
                  (s, idx) => {
                    const items = isMissing ? s.missing : s.submitted;
                    return (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          flexWrap: "wrap",
                        }}
                      >
                        <span
                          style={{
                            minWidth: "140px",
                            fontWeight: 500,
                            fontSize: "0.9rem",
                          }}
                        >
                          {s.name}
                          {!isMissing && s.missing.length > 0 && (
                            <span style={{ color: "#b45309", fontWeight: 400, fontSize: "0.75rem", marginLeft: "6px" }}>
                              ({s.missing.length} missing)
                            </span>
                          )}
                        </span>
                        <div
                          style={{
                            display: "flex",
                            gap: "5px",
                            flexWrap: "wrap",
                          }}
                        >
                          {items.map((a) => (
                            <span
                              key={a}
                              style={{
                                padding: "2px 8px",
                                background: isMissing
                                  ? "rgba(251,191,36,0.15)"
                                  : "rgba(16,185,129,0.15)",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                color: isMissing ? "#b45309" : "#059669",
                                border: isMissing
                                  ? "1px solid rgba(180,83,9,0.3)"
                                  : "1px solid rgba(16,185,129,0.3)",
                              }}
                            >
                              {a}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
