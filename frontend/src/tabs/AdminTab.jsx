import React, { useState, useEffect } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";

function timeAgo(dateStr) {
  if (!dateStr) return "";
  var now = Date.now();
  var then = new Date(dateStr).getTime();
  var diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + " minutes ago";
  if (diff < 86400) return Math.floor(diff / 3600) + " hours ago";
  if (diff < 604800) return Math.floor(diff / 86400) + " days ago";
  return new Date(dateStr).toLocaleDateString();
}

var GRADE_COLORS = {
  A: "#22c55e",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444"
};

export default React.memo(function AdminTab({ school }) {
  var [teachers, setTeachers] = useState([]);
  var [overview, setOverview] = useState({});
  var [activity, setActivity] = useState([]);
  var [selectedTeacher, setSelectedTeacher] = useState(null);
  var [teacherSummary, setTeacherSummary] = useState(null);
  var [summaryLoading, setSummaryLoading] = useState(false);
  var [loading, setLoading] = useState(true);

  useEffect(function() {
    var cancelled = false;
    Promise.all([
      api.getAdminTeachers().catch(function() { return { teachers: [] }; }),
      api.getAdminOverview().catch(function() { return {}; }),
      api.getAdminActivity().catch(function() { return { activity: [] }; })
    ]).then(function(results) {
      if (cancelled) return;
      setTeachers(results[0].teachers || []);
      setOverview(results[1]);
      setActivity(results[2].activity || []);
      setLoading(false);
    });
    return function() { cancelled = true; };
  }, []);

  function handleTeacherClick(teacher) {
    if (selectedTeacher && selectedTeacher.id === teacher.id) {
      setSelectedTeacher(null);
      setTeacherSummary(null);
      return;
    }
    setSelectedTeacher(teacher);
    setSummaryLoading(true);
    setTeacherSummary(null);
    api.getAdminTeacherSummary(teacher.id).then(function(data) {
      setTeacherSummary(data);
      setSummaryLoading(false);
    }).catch(function() {
      setSummaryLoading(false);
    });
  }

  if (loading) {
    return React.createElement("div", { className: "glass-card", style: { padding: "80px", textAlign: "center" } },
      React.createElement("div", { style: { display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" } }),
      React.createElement("h2", { style: { marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 } }, "Loading Admin Dashboard...")
    );
  }

  var gradeDistribution = overview.grade_distribution || {};
  var totalGraded = 0;
  var gradeKeys = ["A", "B", "C", "D", "F"];
  gradeKeys.forEach(function(g) { totalGraded += (gradeDistribution[g] || 0); });

  return React.createElement("div", { className: "fade-in" },

    // Panel 1: Teacher Overview
    React.createElement("div", { className: "glass-card", style: { padding: "25px", marginBottom: "20px" } },
      React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" } },
        React.createElement("h2", { style: { fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" } },
          React.createElement(Icon, { name: "Users", size: 22 }),
          "Teachers at " + (school || "School")
        ),
        React.createElement("span", { style: { background: "var(--accent-primary)", color: "#fff", borderRadius: "12px", padding: "4px 14px", fontSize: "0.85rem", fontWeight: 600 } },
          teachers.length
        )
      ),
      React.createElement("div", { style: { overflowX: "auto" } },
        React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" } },
          React.createElement("thead", null,
            React.createElement("tr", null,
              ["Name", "Email", "Classes", "Students", "Assessments", "Last Activity"].map(function(col) {
                return React.createElement("th", { key: col, style: { padding: "10px 14px", textAlign: "left", borderBottom: "2px solid var(--border)", fontWeight: 600, color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.5px" } }, col);
              })
            )
          ),
          React.createElement("tbody", null,
            teachers.length === 0
              ? React.createElement("tr", null,
                  React.createElement("td", { colSpan: 6, style: { padding: "30px", textAlign: "center", color: "var(--text-secondary)" } }, "No teachers found")
                )
              : teachers.map(function(t) {
                  var isUnregistered = !t.user_id;
                  var isSelected = selectedTeacher && selectedTeacher.id === t.id;
                  return React.createElement("tr", {
                    key: t.id || t.email,
                    onClick: function() { if (!isUnregistered) handleTeacherClick(t); },
                    style: {
                      cursor: isUnregistered ? "default" : "pointer",
                      background: isSelected ? "rgba(139, 92, 246, 0.08)" : "transparent",
                      opacity: isUnregistered ? 0.5 : 1,
                      transition: "background 0.15s"
                    }
                  },
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)", fontWeight: 500 } },
                      t.name || "—",
                      isUnregistered ? React.createElement("span", { style: { marginLeft: "8px", background: "var(--glass-border)", color: "var(--text-secondary)", borderRadius: "8px", padding: "2px 8px", fontSize: "0.7rem", fontWeight: 600 } }, "Not registered") : null
                    ),
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)", color: "var(--text-secondary)" } }, t.email || "—"),
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)" } }, t.class_count != null ? t.class_count : "—"),
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)" } }, t.student_count != null ? t.student_count : "—"),
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)" } }, t.assessment_count != null ? t.assessment_count : "—"),
                    React.createElement("td", { style: { padding: "12px 14px", borderBottom: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "0.85rem" } }, t.last_activity ? timeAgo(t.last_activity) : "—")
                  );
                })
          )
        )
      )
    ),

    // Panel 2: School-Wide Analytics
    React.createElement("div", { className: "glass-card", style: { padding: "25px", marginBottom: "20px" } },
      React.createElement("h2", { style: { fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" } },
        React.createElement(Icon, { name: "BarChart3", size: 22 }),
        "School-Wide Analytics"
      ),
      // Summary cards
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "15px", marginBottom: "25px" } },
        [
          { label: "Total Teachers", value: overview.total_teachers || 0, icon: "Users", color: "#8b5cf6" },
          { label: "Total Students", value: overview.total_students || 0, icon: "GraduationCap", color: "#3b82f6" },
          { label: "Total Assessments", value: overview.total_assessments || 0, icon: "FileText", color: "#22c55e" },
          { label: "Average Score", value: overview.average_score != null ? (Math.round(overview.average_score * 10) / 10) + "%" : "—", icon: "Target", color: "#f59e0b" }
        ].map(function(card) {
          return React.createElement("div", { key: card.label, style: { background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "14px", padding: "20px", textAlign: "center" } },
            React.createElement("div", { style: { marginBottom: "8px" } },
              React.createElement(Icon, { name: card.icon, size: 24, color: card.color })
            ),
            React.createElement("div", { style: { fontSize: "1.8rem", fontWeight: 700, color: card.color } }, card.value),
            React.createElement("div", { style: { fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.5px" } }, card.label)
          );
        })
      ),
      // Grade distribution bars
      totalGraded > 0 ? React.createElement("div", null,
        React.createElement("h3", { style: { fontSize: "1rem", fontWeight: 600, marginBottom: "12px", color: "var(--text-secondary)" } }, "Grade Distribution"),
        gradeKeys.map(function(grade) {
          var count = gradeDistribution[grade] || 0;
          var pct = totalGraded > 0 ? Math.round((count / totalGraded) * 100) : 0;
          return React.createElement("div", { key: grade, style: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" } },
            React.createElement("span", { style: { width: "20px", fontWeight: 700, fontSize: "0.9rem" } }, grade),
            React.createElement("div", { style: { flex: 1, height: "24px", background: "var(--glass-bg)", borderRadius: "6px", overflow: "hidden", border: "1px solid var(--glass-border)" } },
              React.createElement("div", { style: { width: pct + "%", height: "100%", background: GRADE_COLORS[grade], borderRadius: "6px", transition: "width 0.5s ease", minWidth: count > 0 ? "4px" : "0" } })
            ),
            React.createElement("span", { style: { width: "70px", textAlign: "right", fontSize: "0.85rem", color: "var(--text-secondary)" } }, count + " (" + pct + "%)")
          );
        })
      ) : React.createElement("div", { style: { textAlign: "center", color: "var(--text-secondary)", padding: "20px" } }, "No graded assessments yet")
    ),

    // Panel 3: Teacher Drill-Down
    selectedTeacher ? React.createElement("div", { className: "glass-card", style: { padding: "25px", marginBottom: "20px" } },
      React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" } },
        React.createElement("h2", { style: { fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" } },
          React.createElement(Icon, { name: "User", size: 22 }),
          (selectedTeacher.name || selectedTeacher.email) + " — Details"
        ),
        React.createElement("button", {
          onClick: function() { setSelectedTeacher(null); setTeacherSummary(null); },
          className: "btn",
          style: { padding: "8px 16px", fontSize: "0.85rem" }
        }, "Close")
      ),
      summaryLoading
        ? React.createElement("div", { style: { textAlign: "center", padding: "30px", color: "var(--text-secondary)" } }, "Loading teacher details...")
        : teacherSummary
          ? React.createElement("div", null,
              // Classes
              React.createElement("h3", { style: { fontSize: "1rem", fontWeight: 600, marginBottom: "10px" } }, "Classes"),
              (teacherSummary.classes || []).length > 0
                ? React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "20px" } },
                    (teacherSummary.classes || []).map(function(cls, i) {
                      return React.createElement("span", { key: i, style: { background: "rgba(139, 92, 246, 0.1)", border: "1px solid rgba(139, 92, 246, 0.2)", borderRadius: "8px", padding: "6px 14px", fontSize: "0.85rem", fontWeight: 500 } },
                        cls.name + " (" + (cls.student_count || 0) + " students)"
                      );
                    })
                  )
                : React.createElement("div", { style: { color: "var(--text-secondary)", marginBottom: "20px", fontSize: "0.9rem" } }, "No classes"),

              // Recent assessments
              React.createElement("h3", { style: { fontSize: "1rem", fontWeight: 600, marginBottom: "10px" } }, "Recent Assessments"),
              (teacherSummary.recent_assessments || []).length > 0
                ? React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", marginBottom: "20px" } },
                    React.createElement("thead", null,
                      React.createElement("tr", null,
                        ["Title", "Submissions", "Avg Score"].map(function(col) {
                          return React.createElement("th", { key: col, style: { padding: "8px 12px", textAlign: "left", borderBottom: "2px solid var(--border)", fontWeight: 600, color: "var(--text-secondary)", fontSize: "0.75rem", textTransform: "uppercase" } }, col);
                        })
                      )
                    ),
                    React.createElement("tbody", null,
                      (teacherSummary.recent_assessments || []).map(function(a, i) {
                        return React.createElement("tr", { key: i },
                          React.createElement("td", { style: { padding: "8px 12px", borderBottom: "1px solid var(--border)" } }, a.title || "—"),
                          React.createElement("td", { style: { padding: "8px 12px", borderBottom: "1px solid var(--border)" } }, a.submission_count != null ? a.submission_count : "—"),
                          React.createElement("td", { style: { padding: "8px 12px", borderBottom: "1px solid var(--border)" } }, a.avg_score != null ? (Math.round(a.avg_score * 10) / 10) + "%" : "—")
                        );
                      })
                    )
                  )
                : React.createElement("div", { style: { color: "var(--text-secondary)", marginBottom: "20px", fontSize: "0.9rem" } }, "No assessments"),

              // Recent activity
              React.createElement("h3", { style: { fontSize: "1rem", fontWeight: 600, marginBottom: "10px" } }, "Recent Activity"),
              (teacherSummary.recent_activity || []).length > 0
                ? React.createElement("div", null,
                    (teacherSummary.recent_activity || []).map(function(entry, i) {
                      return React.createElement("div", { key: i, style: { padding: "8px 0", borderBottom: i < (teacherSummary.recent_activity.length - 1) ? "1px solid var(--border)" : "none", fontSize: "0.85rem" } },
                        React.createElement("span", { style: { color: "var(--text-secondary)" } }, entry.action || ""),
                        React.createElement("span", { style: { marginLeft: "10px", color: "var(--text-secondary)", fontSize: "0.8rem", opacity: 0.7 } }, timeAgo(entry.timestamp))
                      );
                    })
                  )
                : React.createElement("div", { style: { color: "var(--text-secondary)", fontSize: "0.9rem" } }, "No recent activity")
            )
          : React.createElement("div", { style: { textAlign: "center", padding: "20px", color: "var(--text-secondary)" } }, "Could not load teacher details")
    ) : null,

    // Panel 4: Activity Feed
    React.createElement("div", { className: "glass-card", style: { padding: "25px" } },
      React.createElement("h2", { style: { fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" } },
        React.createElement(Icon, { name: "Activity", size: 22 }),
        "Recent Activity"
      ),
      activity.length > 0
        ? React.createElement("div", null,
            activity.slice(0, 50).map(function(entry, i) {
              return React.createElement("div", { key: i, style: { padding: "10px 0", borderBottom: i < Math.min(activity.length, 50) - 1 ? "1px solid var(--border)" : "none", display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" } },
                React.createElement("span", { style: { fontWeight: 600, fontSize: "0.9rem" } }, entry.teacher_name || "Unknown"),
                React.createElement("span", { style: { color: "var(--text-secondary)", fontSize: "0.85rem" } }, entry.action || ""),
                React.createElement("span", { style: { marginLeft: "auto", color: "var(--text-secondary)", fontSize: "0.8rem", opacity: 0.7, whiteSpace: "nowrap" } }, timeAgo(entry.timestamp))
              );
            })
          )
        : React.createElement("div", { style: { textAlign: "center", color: "var(--text-secondary)", padding: "30px" } }, "No recent activity")
    )
  );
});
