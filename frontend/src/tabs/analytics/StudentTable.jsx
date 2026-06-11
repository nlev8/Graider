import React, { useState } from "react";
import Icon from "../../components/Icon";

// StudentTable — memoized to skip re-render when selectedStudent changes for non-table reasons
const StudentTable = React.memo(function StudentTable({
  filteredAnalytics, selectedStudent, onStudentClick,
}) {
  const [studentSortCol, setStudentSortCol] = useState("name");
  const [studentSortDir, setStudentSortDir] = useState("asc");

  return (
      <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 500px" }}>
        <h3
          style={{
            fontSize: "1.1rem",
            fontWeight: 700,
            marginBottom: "15px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Icon name="Users" size={20} />
          All Students Overview
        </h3>
        <table>
          <thead>
            <tr>
              {[
                { key: "name", label: "Student" },
                { key: "assignments", label: "Assignments" },
                { key: "average", label: "Average" },
                { key: "content", label: "Content", small: true },
                { key: "completeness", label: "Complete", small: true },
                { key: "writing", label: "Writing", small: true },
                { key: "effort", label: "Effort", small: true },
                { key: "trend", label: "Trend" },
              ].map((col) => (
                <th
                  key={col.key}
                  onClick={() => {
                    if (studentSortCol === col.key) {
                      setStudentSortDir(studentSortDir === "asc" ? "desc" : "asc");
                    } else {
                      setStudentSortCol(col.key);
                      setStudentSortDir(col.key === "name" ? "asc" : "desc");
                    }
                  }}
                  style={{
                    textAlign: col.key === "name" ? "left" : "center",
                    fontSize: col.small ? "0.8rem" : undefined,
                    cursor: "pointer",
                    userSelect: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col.label}
                  {studentSortCol === col.key ? (
                    <span style={{ marginLeft: "4px", fontSize: "0.7rem" }}>
                      {studentSortDir === "asc" ? "\u25B2" : "\u25BC"}
                    </span>
                  ) : (
                    <span style={{ marginLeft: "4px", fontSize: "0.7rem", opacity: 0.3 }}>{"\u25BC"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(() => {
              const catStats = filteredAnalytics.category_stats || [];
              const rows = (filteredAnalytics.student_progress || []).slice();
              const trendOrder = { improving: 2, steady: 1, declining: 0 };
              rows.sort((a, b) => {
                let av, bv;
                if (studentSortCol === "name") {
                  av = a.name.toLowerCase();
                  bv = b.name.toLowerCase();
                } else if (studentSortCol === "assignments") {
                  av = (a.grades || []).length;
                  bv = (b.grades || []).length;
                } else if (studentSortCol === "average") {
                  av = a.average || 0;
                  bv = b.average || 0;
                } else if (studentSortCol === "trend") {
                  av = trendOrder[a.trend] ?? 1;
                  bv = trendOrder[b.trend] ?? 1;
                } else {
                  const ac = catStats.find((c) => c.name === a.name);
                  const bc = catStats.find((c) => c.name === b.name);
                  av = ac ? (ac[studentSortCol] || 0) : 0;
                  bv = bc ? (bc[studentSortCol] || 0) : 0;
                }
                if (av < bv) return studentSortDir === "asc" ? -1 : 1;
                if (av > bv) return studentSortDir === "asc" ? 1 : -1;
                return 0;
              });
              return rows;
            })().map(
              (s, i) => (
                <tr
                  key={i}
                  onClick={() => onStudentClick(s.name)}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedStudent === s.name
                        ? "rgba(99,102,241,0.2)"
                        : "transparent",
                  }}
                >
                  <td
                    style={{
                      fontWeight: 600,
                      textDecoration: "underline dotted",
                    }}
                  >
                    {s.name}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {(s.grades || []).length}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span
                      style={{
                        padding: "4px 12px",
                        borderRadius: "20px",
                        fontWeight: 700,
                        background:
                          s.average >= 90
                            ? "rgba(74,222,128,0.2)"
                            : s.average >= 80
                              ? "rgba(96,165,250,0.2)"
                              : s.average >= 70
                                ? "rgba(251,191,36,0.2)"
                                : "rgba(248,113,113,0.2)",
                        color:
                          s.average >= 90
                            ? "#4ade80"
                            : s.average >= 80
                              ? "#60a5fa"
                              : s.average >= 70
                                ? "#fbbf24"
                                : "#f87171",
                      }}
                    >
                      {s.average}%
                    </span>
                  </td>
                  {(() => {
                    const cats = (filteredAnalytics.category_stats || []).find((c) => c.name === s.name);
                    const catKeys = ["content", "completeness", "writing", "effort"];
                    return catKeys.map((key) => {
                      const val = cats ? (cats[key] || 0) : 0;
                      const barColor = val >= 80 ? "#4ade80" : val >= 60 ? "#60a5fa" : val >= 40 ? "#fbbf24" : "#f87171";
                      return (
                        <td key={key} style={{ textAlign: "center", padding: "8px 6px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "4px", justifyContent: "center" }}>
                            <div style={{ width: "40px", height: "6px", background: "rgba(148,163,184,0.15)", borderRadius: "3px", overflow: "hidden" }}>
                              <div style={{ height: "100%", width: Math.min(val, 100) + "%", background: barColor, borderRadius: "3px" }} />
                            </div>
                            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: barColor, minWidth: "28px" }}>{val}%</span>
                          </div>
                        </td>
                      );
                    });
                  })()}
                  <td style={{ textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        color:
                          s.trend === "improving"
                            ? "#4ade80"
                            : s.trend === "declining"
                              ? "#f87171"
                              : "#94a3b8",
                      }}
                    >
                      <Icon
                        name={
                          s.trend === "improving"
                            ? "TrendingUp"
                            : s.trend === "declining"
                              ? "TrendingDown"
                              : "Minus"
                        }
                        size={16}
                      />
                      {s.trend}
                    </span>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>

  );
});

export default StudentTable;
