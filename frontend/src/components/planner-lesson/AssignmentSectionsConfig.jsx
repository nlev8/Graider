import React from "react";
import Icon from "../Icon";

export default function AssignmentSectionsConfig(props) {
  const { assignmentQuestionCounts, assignmentSectionsOpen, setAssignmentQuestionCounts, setAssignmentSectionsOpen, unitConfig } = props;
  if (unitConfig.type !== "Assignment") return null;
  return (
                            <div style={{
                              border: "1px solid var(--glass-border)",
                              borderRadius: "10px",
                              overflow: "hidden",
                            }}>
                              <button
                                type="button"
                                onClick={() => setAssignmentSectionsOpen(!assignmentSectionsOpen)}
                                style={{
                                  width: "100%",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  background: "var(--glass-bg)",
                                  border: "none",
                                  cursor: "pointer",
                                  padding: "10px 14px",
                                  color: "inherit",
                                }}
                              >
                                <span style={{ fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                                  <Icon name="LayoutGrid" size={16} /> Sections
                                  <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--text-muted)" }}>
                                    ({Object.values(assignmentQuestionCounts).filter(function(v) { return v > 0; }).length} types)
                                  </span>
                                </span>
                                <Icon name={assignmentSectionsOpen ? "ChevronUp" : "ChevronDown"} size={16} />
                              </button>
                              {assignmentSectionsOpen && (
                                <div style={{ padding: "10px 14px", borderTop: "1px solid var(--glass-border)" }}>
                                  {(function() {
                                    var totalAssigned = Object.values(assignmentQuestionCounts).reduce(function(a, b) { return a + b; }, 0);
                                    var totalTarget = unitConfig.totalQuestions || 10;
                                    var statusColor = totalAssigned === totalTarget ? "#22c55e" : totalAssigned > totalTarget ? "#ef4444" : "#f59e0b";
                                    return (
                                      React.createElement('div', {
                                        style: { fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px", color: statusColor }
                                      },
                                        totalAssigned + "/" + totalTarget + " assigned" +
                                        (totalAssigned < totalTarget ? " — AI will distribute " + (totalTarget - totalAssigned) + " remaining" : "") +
                                        (totalAssigned > totalTarget ? " — exceeds total by " + (totalAssigned - totalTarget) : "")
                                      )
                                    );
                                  })()}
                                  {[
                                    { key: "multiple_choice", label: "Multiple Choice", group: "core" },
                                    { key: "short_answer", label: "Short Answer", group: "core" },
                                    { key: "math_computation", label: "Math Computation", group: "stem" },
                                    { key: "geometry_visual", label: "Geometry", group: "stem" },
                                    { key: "graphing", label: "Graphing", group: "stem" },
                                    { key: "data_analysis", label: "Data Analysis", group: "stem" },
                                    { key: "extended_writing", label: "Extended Writing", group: "optional" },
                                    { key: "vocabulary", label: "Vocabulary", group: "optional" },
                                    { key: "true_false", label: "True / False", group: "optional" },
                                    { key: "florida_fast", label: "FL FAST Items", group: "optional" },
                                  ].map(function(cat, idx, arr) {
                                    var prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                    var showDivider = cat.group !== prevGroup;
                                    var groupLabels = { core: "Core", stem: "STEM", optional: "Optional" };
                                    var groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                    var count = assignmentQuestionCounts[cat.key] || 0;
                                    return (
                                      React.createElement('div', { key: cat.key },
                                        showDivider ? React.createElement('div', {
                                          style: { fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase",
                                            letterSpacing: "0.05em", color: groupColors[cat.group],
                                            marginTop: idx > 0 ? "4px" : 0, marginBottom: "2px" }
                                        }, groupLabels[cat.group]) : null,
                                        React.createElement('div', {
                                          style: { display: "flex", alignItems: "center", justifyContent: "space-between",
                                            padding: "4px 8px", borderRadius: "6px", fontSize: "0.82rem",
                                            background: count > 0 ? "rgba(99,102,241,0.1)" : "transparent" }
                                        },
                                          React.createElement('span', { style: { color: count > 0 ? "var(--text-primary)" : "var(--text-muted)" } }, cat.label),
                                          React.createElement('input', {
                                            type: "number",
                                            min: 0,
                                            max: unitConfig.totalQuestions || 50,
                                            value: count,
                                            onChange: function(e) {
                                              var val = parseInt(e.target.value) || 0;
                                              var updated = Object.assign({}, assignmentQuestionCounts);
                                              updated[cat.key] = Math.max(0, val);
                                              setAssignmentQuestionCounts(updated);
                                            },
                                            style: { width: "50px", padding: "3px 6px", borderRadius: "6px",
                                              border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                                              color: "var(--text-primary)", fontSize: "0.82rem", textAlign: "center" }
                                          })
                                        )
                                      )
                                    );
                                  })}
                                </div>
                              )}
                            </div>
  );
}
