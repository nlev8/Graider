import React from "react";
import Icon from "../Icon";

export default function ProjectPhasesView(props) {
  const { lessonPlan } = props;
  return (
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "20px",
                              }}
                            >
                              {lessonPlan.driving_question && (
                                <div
                                  style={{
                                    background: "rgba(99,102,241,0.1)",
                                    borderRadius: "12px",
                                    padding: "15px",
                                    border: "1px solid rgba(99,102,241,0.2)",
                                  }}
                                >
                                  <strong style={{ color: "#818cf8" }}>Driving Question:</strong>{" "}
                                  <span style={{ fontSize: "0.95rem" }}>{lessonPlan.driving_question}</span>
                                </div>
                              )}
                              {lessonPlan.total_points && (
                                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                  Total: {lessonPlan.total_points} points
                                </p>
                              )}
                              {(lessonPlan.phases || []).map((phase, i) => (
                                <div
                                  key={i}
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "25px",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      gap: "15px",
                                      marginBottom: "15px",
                                      paddingBottom: "10px",
                                      borderBottom: "1px solid var(--glass-border)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "40px",
                                        height: "40px",
                                        borderRadius: "10px",
                                        background: "linear-gradient(135deg, #10b981, #06b6d4)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontWeight: 700,
                                        fontSize: "1rem",
                                        flexShrink: 0,
                                      }}
                                    >
                                      {phase.phase || i + 1}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "4px" }}>
                                        {phase.name}
                                      </h3>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {phase.duration}
                                      </span>
                                    </div>
                                  </div>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "10px", lineHeight: 1.5 }}>
                                    {phase.description}
                                  </p>
                                  {phase.tasks && (
                                    <ul style={{ margin: "0 0 10px 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {phase.tasks.map((t, ti) => (
                                        <li key={ti} style={{ marginBottom: "4px" }}>{t}</li>
                                      ))}
                                    </ul>
                                  )}
                                  {phase.deliverable && (
                                    <p style={{ fontSize: "0.85rem", color: "#10b981" }}>
                                      <strong>Deliverable:</strong> {phase.deliverable}
                                    </p>
                                  )}
                                </div>
                              ))}
                              {lessonPlan.final_deliverable && (
                                <div
                                  style={{
                                    background: "rgba(16,185,129,0.1)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                    border: "1px solid rgba(16,185,129,0.2)",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px", color: "#10b981" }}>
                                    <Icon name="Award" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Final Deliverable
                                  </h3>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "8px" }}>
                                    <strong>Format:</strong> {lessonPlan.final_deliverable.format}
                                  </p>
                                  {lessonPlan.final_deliverable.requirements && (
                                    <ul style={{ margin: "0 0 0 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {lessonPlan.final_deliverable.requirements.map((r, ri) => (
                                        <li key={ri}>{r}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              )}
                              {lessonPlan.rubric && lessonPlan.rubric.criteria && (
                                <div
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px" }}>
                                    <Icon name="ClipboardList" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Rubric
                                  </h3>
                                  {lessonPlan.rubric.criteria.map((c, ci) => (
                                    <div key={ci} style={{ marginBottom: "10px", paddingBottom: "10px", borderBottom: ci < lessonPlan.rubric.criteria.length - 1 ? "1px solid var(--glass-border)" : "none" }}>
                                      <strong style={{ fontSize: "0.9rem" }}>{c.name}</strong>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "8px" }}>({c.points} pts)</span>
                                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "4px" }}>{c.description}</p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
  );
}
