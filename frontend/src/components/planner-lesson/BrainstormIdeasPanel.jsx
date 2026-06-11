import React from "react";
import Icon from "../Icon";

export default function BrainstormIdeasPanel(props) {
  const { brainstormIdeas, lessonPlan, lessonVariations, selectedIdea, setBrainstormIdeas, setSelectedIdea, setUnitConfig, unitConfig } = props;
  if (!(brainstormIdeas.length > 0 && !lessonPlan && lessonVariations.length === 0)) return null;
  return (
                          <div
                            className="glass-card"
                            style={{ padding: "25px", marginBottom: "20px" }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "20px",
                              }}
                            >
                              <h3
                                style={{
                                  fontSize: "1.2rem",
                                  fontWeight: 700,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                  margin: 0,
                                }}
                              >
                                <Icon
                                  name="Lightbulb"
                                  size={24}
                                  style={{ color: "#f59e0b" }}
                                />{" "}
                                {unitConfig.type + " Ideas"}
                              </h3>
                              <button
                                onClick={() => { setBrainstormIdeas([]); setSelectedIdea(null); }}
                                className="btn btn-secondary"
                                style={{
                                  padding: "6px 12px",
                                  fontSize: "0.85rem",
                                }}
                              >
                                <Icon name="X" size={14} /> Clear
                              </button>
                            </div>
                            <p
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                                marginBottom: "20px",
                              }}
                            >
                              Select an idea to develop into a full lesson plan,
                              or use it as inspiration.
                            </p>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fill, minmax(300px, 1fr))",
                                gap: "15px",
                              }}
                            >
                              {brainstormIdeas.map((idea) => (
                                <div
                                  key={idea.id}
                                  onClick={() => {
                                    setSelectedIdea(
                                      selectedIdea?.id === idea.id
                                        ? null
                                        : idea,
                                    );
                                    if (selectedIdea?.id !== idea.id) {
                                      setUnitConfig((prev) => ({
                                        ...prev,
                                        title: idea.title,
                                      }));
                                    }
                                  }}
                                  style={{
                                    padding: "20px",
                                    borderRadius: "12px",
                                    background:
                                      selectedIdea?.id === idea.id
                                        ? "rgba(99,102,241,0.15)"
                                        : "var(--input-bg)",
                                    border:
                                      selectedIdea?.id === idea.id
                                        ? "2px solid var(--accent-primary)"
                                        : "1px solid var(--glass-border)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "flex-start",
                                      marginBottom: "10px",
                                    }}
                                  >
                                    <h4
                                      style={{
                                        fontWeight: 600,
                                        fontSize: "1.05rem",
                                        margin: 0,
                                        flex: 1,
                                      }}
                                    >
                                      {idea.title}
                                    </h4>
                                    <span
                                      style={{
                                        padding: "4px 12px",
                                        borderRadius: "12px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginLeft: "10px",
                                        background:
                                          idea.approach === "Activity-Based"
                                            ? "rgba(16,185,129,0.2)"
                                            : idea.approach === "Discussion"
                                              ? "rgba(99,102,241,0.2)"
                                              : idea.approach === "Project"
                                                ? "rgba(245,158,11,0.2)"
                                                : idea.approach === "Simulation"
                                                  ? "rgba(236,72,153,0.2)"
                                                  : "rgba(107,114,128,0.2)",
                                        color:
                                          idea.approach === "Activity-Based"
                                            ? "#10b981"
                                            : idea.approach === "Discussion"
                                              ? "#6366f1"
                                              : idea.approach === "Project"
                                                ? "#f59e0b"
                                                : idea.approach === "Simulation"
                                                  ? "#ec4899"
                                                  : "#6b7280",
                                      }}
                                    >
                                      {idea.approach}
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                      marginBottom: "12px",
                                      lineHeight: 1.5,
                                    }}
                                  >
                                    {idea.brief}
                                  </p>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                      marginBottom: "6px",
                                    }}
                                  >
                                    <strong>Hook:</strong> {idea.hook}
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    <strong>Activity:</strong>{" "}
                                    {idea.key_activity}
                                  </div>
                                  {idea.tools_used && idea.tools_used !== "None - hands-on activity" && (
                                    <div
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                        marginTop: "6px",
                                        display: "flex",
                                        alignItems: "flex-start",
                                        gap: "6px",
                                      }}
                                    >
                                      <Icon name="Monitor" size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                                      <span><strong>Tools:</strong> {idea.tools_used}</span>
                                    </div>
                                  )}
                                  {selectedIdea?.id === idea.id && (
                                    <div
                                      style={{
                                        marginTop: "12px",
                                        padding: "10px",
                                        background: "rgba(99,102,241,0.1)",
                                        borderRadius: "8px",
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                      }}
                                    >
                                      <Icon
                                        name="CheckCircle"
                                        size={14}
                                        style={{
                                          marginRight: "6px",
                                          verticalAlign: "middle",
                                        }}
                                      />
                                      Selected - Click "Generate" to create
                                      lesson plan
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
  );
}
