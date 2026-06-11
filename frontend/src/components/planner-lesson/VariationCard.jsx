import React from "react";
import Icon from "../Icon";

export default function VariationCard(props) {
  const { idx, setLessonPlan, setLessonVariations, unitConfig, variation } = props;
  return (
                              <div
                                style={{
                                  padding: "20px",
                                  background: "var(--input-bg)",
                                  borderRadius: "12px",
                                  border: "1px solid var(--glass-border)",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "flex-start",
                                    marginBottom: "15px",
                                  }}
                                >
                                  <div>
                                    <span
                                      style={{
                                        display: "inline-block",
                                        padding: "4px 12px",
                                        borderRadius: "15px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginBottom: "8px",
                                        background:
                                          idx === 0
                                            ? "rgba(16,185,129,0.2)"
                                            : idx === 1
                                              ? "rgba(99,102,241,0.2)"
                                              : "rgba(245,158,11,0.2)",
                                        color:
                                          idx === 0
                                            ? "#10b981"
                                            : idx === 1
                                              ? "#6366f1"
                                              : "#f59e0b",
                                      }}
                                    >
                                      {variation.approach ||
                                        `Variation ${idx + 1}`}
                                    </span>
                                    <h3
                                      style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 600,
                                        margin: "8px 0",
                                      }}
                                    >
                                      {variation.title}
                                    </h3>
                                    <p
                                      style={{
                                        color: "var(--text-secondary)",
                                        fontSize: "0.9rem",
                                        lineHeight: 1.5,
                                      }}
                                    >
                                      {variation.overview}
                                    </p>
                                  </div>
                                  <button
                                    onClick={() => {
                                      setLessonPlan(variation);
                                      setLessonVariations([]);
                                    }}
                                    className="btn btn-primary"
                                    style={{ flexShrink: 0 }}
                                  >
                                    <Icon name="Check" size={16} /> {"Use This " + (unitConfig.type || "Plan")}
                                  </button>
                                </div>
                                {/* Content preview - varies by type */}
                                {variation.sections ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Sections:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.sections.map((s, si) => (
                                        <li key={si}>
                                          {s.name} ({s.points || 0} pts, {(s.questions || []).length} questions)
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : variation.phases ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Phases:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.phases.map((p, pi) => (
                                        <li key={pi}>
                                          {p.name} ({p.duration})
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : (
                                  <>
                                    {variation.essential_questions && (
                                      <div style={{ marginTop: "10px" }}>
                                        <strong
                                          style={{
                                            fontSize: "0.85rem",
                                            color: "var(--text-primary)",
                                          }}
                                        >
                                          Essential Questions:
                                        </strong>
                                        <ul
                                          style={{
                                            margin: "5px 0 0 20px",
                                            fontSize: "0.85rem",
                                            color: "var(--text-secondary)",
                                          }}
                                        >
                                          {variation.essential_questions
                                            .slice(0, 2)
                                            .map((q, i) => (
                                              <li key={i}>{q}</li>
                                            ))}
                                        </ul>
                                      </div>
                                    )}
                                    {variation.days && (
                                      <div
                                        style={{
                                          marginTop: "10px",
                                          fontSize: "0.85rem",
                                          color: "var(--text-muted)",
                                        }}
                                      >
                                        <Icon
                                          name="Calendar"
                                          size={14}
                                          style={{
                                            marginRight: "6px",
                                            verticalAlign: "middle",
                                          }}
                                        />
                                        {variation.days.length} day
                                        {variation.days.length !== 1
                                          ? "s"
                                          : ""}{" "}
                                        planned
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
  );
}
