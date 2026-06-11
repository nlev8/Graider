import React from "react";
import Icon from "../Icon";
import RawSubmissionView from "./RawSubmissionView";

export default function SubmissionPanel(props) {
  const { r, reviewModalTab, setReviewModalTab } = props;
  return (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      background: "var(--glass-bg)",
                      borderRadius: "16px",
                      border: "1px solid var(--glass-border)",
                      overflow: "hidden",
                    }}
                  >
                    {/* Header with tabs */}
                    <div
                      style={{
                        padding: "16px 20px",
                        borderBottom: "1px solid var(--glass-border)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => setReviewModalTab("detected")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalTab === "detected"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalTab === "detected"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="CheckCircle" size={14} />
                          Responses
                        </button>
                        <button
                          onClick={() => setReviewModalTab("raw")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalTab === "raw"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalTab === "raw"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="FileText" size={14} />
                          Raw Text
                        </button>
                      </div>
                    </div>

                    {/* Tab Content */}
                    <div style={{ flex: 1, overflow: "auto", padding: "20px" }}>
                      {reviewModalTab === "detected" ? (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "16px",
                          }}
                        >
                          {/* Student Responses */}
                          {r.student_responses &&
                          r.student_responses.length > 0 ? (
                            <div>
                              <div
                                style={{
                                  fontWeight: 600,
                                  marginBottom: "12px",
                                  color: "#4ade80",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                  fontSize: "0.9rem",
                                }}
                              >
                                <Icon name="CheckCircle" size={16} />
                                Detected Responses ({r.student_responses.length}
                                )
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "10px",
                                }}
                              >
                                {r.student_responses.map((resp, i) => (
                                  <div
                                    key={i}
                                    style={{
                                      padding: "14px 16px",
                                      background: "rgba(74,222,128,0.08)",
                                      borderRadius: "10px",
                                      fontSize: "0.9rem",
                                      color: "var(--text-primary)",
                                      border: "1px solid rgba(74,222,128,0.2)",
                                      lineHeight: 1.5,
                                    }}
                                  >
                                    {resp}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div
                              style={{
                                padding: "30px",
                                textAlign: "center",
                                color: "var(--text-muted)",
                                fontSize: "0.9rem",
                              }}
                            >
                              No student responses detected
                            </div>
                          )}

                          {/* Unanswered Questions */}
                          {r.unanswered_questions &&
                            r.unanswered_questions.length > 0 && (
                              <div style={{ marginTop: "8px" }}>
                                <div
                                  style={{
                                    fontWeight: 600,
                                    marginBottom: "12px",
                                    color: "#fbbf24",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    fontSize: "0.9rem",
                                  }}
                                >
                                  <Icon name="AlertCircle" size={16} />
                                  Unanswered ({r.unanswered_questions.length})
                                </div>
                                <div
                                  style={{
                                    padding: "14px 16px",
                                    background: "rgba(251,191,36,0.08)",
                                    borderRadius: "10px",
                                    fontSize: "0.9rem",
                                    color: "var(--text-secondary)",
                                    border: "1px solid rgba(251,191,36,0.2)",
                                    lineHeight: 1.6,
                                  }}
                                >
                                  {r.unanswered_questions.join(" • ")}
                                </div>
                              </div>
                            )}
                        </div>
                      ) : (
                        <RawSubmissionView r={r} />
                      )}
                    </div>
                  </div>
  );
}
