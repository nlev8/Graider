import React from "react";
import Icon from "../Icon";

export default function SectionCategoriesCard(props) {
  const { assessmentConfig, distributePoints, distributeQuestions, sectionsDropdownOpen, setAssessmentConfig, setSectionsDropdownOpen } = props;
  return (
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <button
                            type="button"
                            onClick={() => setSectionsDropdownOpen(!sectionsDropdownOpen)}
                            style={{
                              width: "100%",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              padding: 0,
                              color: "inherit",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1rem",
                                fontWeight: 700,
                                margin: 0,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="LayoutGrid" size={18} /> Assessment Sections
                              <span style={{
                                fontSize: "0.75rem",
                                fontWeight: 400,
                                color: "var(--text-muted)",
                                marginLeft: "4px",
                              }}>
                                ({Object.values(assessmentConfig.sectionCategories || {}).filter(function(v) { return v > 0; }).length} types)
                              </span>
                            </h3>
                            <Icon name={sectionsDropdownOpen ? "ChevronUp" : "ChevronDown"} size={18} />
                          </button>

                          {sectionsDropdownOpen && (
                            <div style={{ marginTop: "15px" }}>
                              {(function() {
                                var totalAssigned = Object.values(assessmentConfig.sectionCategories || {}).reduce(function(a, b) { return a + b; }, 0);
                                var totalTarget = assessmentConfig.totalQuestions || 20;
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
                              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>
                                Set question counts per section. FL FAST-aligned defaults are pre-set.
                              </p>
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
                                var groupLabels = { core: "FL FAST Core", stem: "STEM Visuals", optional: "Optional" };
                                var groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                var count = (assessmentConfig.sectionCategories || {})[cat.key] || 0;
                                return (
                                  React.createElement('div', { key: cat.key },
                                    showDivider ? React.createElement('div', {
                                      style: { fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
                                        letterSpacing: "0.05em", color: groupColors[cat.group],
                                        marginTop: idx > 0 ? "8px" : 0, marginBottom: "4px" }
                                    }, groupLabels[cat.group]) : null,
                                    React.createElement('div', {
                                      style: { display: "flex", alignItems: "center", justifyContent: "space-between",
                                        padding: "6px 10px", borderRadius: "8px", fontSize: "0.9rem",
                                        background: count > 0 ? "rgba(99,102,241,0.1)" : "transparent",
                                        border: "1px solid " + (count > 0 ? "rgba(99,102,241,0.3)" : "rgba(255,255,255,0.05)"),
                                        transition: "all 0.2s" }
                                    },
                                      React.createElement('span', { style: { color: count > 0 ? "var(--text-primary)" : "var(--text-muted)", fontWeight: 500 } }, cat.label),
                                      React.createElement('input', {
                                        type: "number",
                                        min: 0,
                                        max: assessmentConfig.totalQuestions || 50,
                                        value: count,
                                        onChange: function(e) {
                                          var val = parseInt(e.target.value) || 0;
                                          var newCats = Object.assign({}, assessmentConfig.sectionCategories);
                                          newCats[cat.key] = Math.max(0, val);
                                          var newTypes = distributeQuestions(assessmentConfig.totalQuestions || 20, newCats);
                                          var newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);
                                          setAssessmentConfig(Object.assign({}, assessmentConfig, {
                                            sectionCategories: newCats,
                                            questionTypes: newTypes,
                                            pointsPerType: newPointsPerType,
                                          }));
                                        },
                                        style: { width: "55px", padding: "4px 6px", borderRadius: "6px",
                                          border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                                          color: "var(--text-primary)", fontSize: "0.9rem", textAlign: "center" }
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
