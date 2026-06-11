import React from "react";
import Icon from "../../components/Icon";

/*
 * PlannerModeToggle — the planner sub-mode button row, relocated verbatim
 * from PlannerTab.jsx (CQ wave-3 split). Pure presentational; destructures
 * exactly what it uses.
 */
export default function PlannerModeToggle({
  plannerMode,
  setPlannerMode,
  fetchPublishedAssessments,
  fetchSharedResources,
  fetchTeacherTags,
  fetchSavedAssessments,
}) {
  return (
                  <div
                    data-tutorial="planner-modes"
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "20px",
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      onClick={() => setPlannerMode("lesson")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "lesson"
                            ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "lesson"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "lesson" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="BookOpen" size={18} />
                      Lesson Planning
                    </button>
                    <button
                      onClick={() => setPlannerMode("assessment")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "assessment"
                            ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "assessment"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "assessment" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="ClipboardCheck" size={18} />
                      Assessment Generator
                    </button>
                    <button
                      onClick={() => {
                        setPlannerMode("dashboard");
                        fetchPublishedAssessments();
                        fetchSharedResources();
                        fetchTeacherTags();
                        fetchSavedAssessments();
                      }}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "dashboard"
                            ? "linear-gradient(135deg, #22c55e, #16a34a)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "dashboard"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "dashboard" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Users" size={18} />
                      Student Portal
                    </button>
                    <button
                      onClick={() => setPlannerMode("calendar")}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "calendar"
                            ? "linear-gradient(135deg, #f59e0b, #d97706)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "calendar"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "calendar" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Calendar" size={18} />
                      Calendar
                    </button>
                    <button
                      onClick={() => { setPlannerMode("tools"); }}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "tools"
                            ? "linear-gradient(135deg, #06b6d4, #0891b2)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "tools"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "tools" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Wrench" size={18} />
                      Tools
                    </button>
                  </div>
  );
}
