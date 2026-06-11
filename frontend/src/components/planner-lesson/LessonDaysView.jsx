import React from "react";
import Icon from "../Icon";

export default function LessonDaysView(props) {
  const { lessonPlan } = props;
  return (
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "30px",
                              }}
                            >
                              {(lessonPlan.days || []).map((day, i) => (
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
                                      marginBottom: "20px",
                                      paddingBottom: "15px",
                                      borderBottom:
                                        "1px solid var(--glass-border)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "50px",
                                        height: "50px",
                                        borderRadius: "12px",
                                        background:
                                          "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontWeight: 700,
                                        fontSize: "1.2rem",
                                      }}
                                    >
                                      {day.day}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <h3
                                        style={{
                                          fontSize: "1.3rem",
                                          fontWeight: 600,
                                          marginBottom: "8px",
                                        }}
                                      >
                                        {day.topic}
                                      </h3>
                                      <p
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "var(--text-primary)",
                                        }}
                                      >
                                        <strong style={{ color: "#10b981" }}>
                                          Objective:
                                        </strong>{" "}
                                        {day.objective}
                                      </p>
                                    </div>
                                  </div>

                                  {day.bell_ringer && (
                                    <div
                                      style={{
                                        marginBottom: "15px",
                                        padding: "15px",
                                        background: "rgba(165,180,252,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(165,180,252,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#a5b4fc",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="Zap" size={14} /> Bell Ringer
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.bell_ringer === "object"
                                          ? day.bell_ringer.prompt
                                          : day.bell_ringer}
                                      </p>
                                    </div>
                                  )}

                                  {day.activity && (
                                    <div
                                      style={{
                                        marginBottom: "15px",
                                        padding: "15px",
                                        background: "rgba(74,222,128,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(74,222,128,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#4ade80",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="Activity" size={14} /> Main
                                        Activity
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.activity === "object"
                                          ? day.activity.description
                                          : day.activity}
                                      </p>
                                    </div>
                                  )}

                                  {day.assessment && (
                                    <div
                                      style={{
                                        padding: "15px",
                                        background: "rgba(248,113,113,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(248,113,113,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#f87171",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="CheckCircle" size={14} />{" "}
                                        Assessment
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.assessment === "object"
                                          ? day.assessment.description
                                          : day.assessment}
                                      </p>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
  );
}
