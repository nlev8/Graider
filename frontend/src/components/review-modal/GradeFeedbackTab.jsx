import React from "react";
import Icon from "../Icon";
import AIReasoningPanel from "../AIReasoningPanel";
import * as api from "../../services/api";

export default function GradeFeedbackTab(props) {
  const { addToast, r, reviewModal, setShowAIReasoning, showAIReasoning, updateGrade } = props;
  return (
                      <div
                        style={{
                          flex: 1,
                          padding: "20px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                          overflow: "auto",
                        }}
                      >
                        <div>
                          <label className="label">Score</label>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "12px",
                            }}
                          >
                            <input
                              type="number"
                              className="input"
                              value={r.score}
                              onChange={(e) =>
                                updateGrade(
                                  reviewModal.index,
                                  "score",
                                  e.target.value,
                                )
                              }
                              style={{ width: "100px" }}
                            />
                            <span
                              style={{
                                padding: "6px 14px",
                                borderRadius: "8px",
                                fontWeight: 700,
                                fontSize: "0.9rem",
                                background:
                                  r.score >= 90
                                    ? "rgba(74,222,128,0.15)"
                                    : r.score >= 80
                                      ? "rgba(96,165,250,0.15)"
                                      : r.score >= 70
                                        ? "rgba(251,191,36,0.15)"
                                        : "rgba(248,113,113,0.15)",
                                color:
                                  r.score >= 90
                                    ? "#4ade80"
                                    : r.score >= 80
                                      ? "#60a5fa"
                                      : r.score >= 70
                                        ? "#fbbf24"
                                        : "#f87171",
                              }}
                            >
                              {r.letter_grade}
                            </span>
                          </div>
                        </div>

                        {/* Late Penalty Info */}
                        {r.late_penalty && (
                          <div style={{ padding: "12px 16px", background: "rgba(245,158,11,0.12)", borderRadius: "10px", border: "1px solid rgba(245,158,11,0.3)" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                              <Icon name="Clock" size={16} style={{ color: "#f59e0b" }} />
                              <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#f59e0b" }}>Late Submission</span>
                            </div>
                            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                              <span>{r.late_penalty.days_late} day{r.late_penalty.days_late !== 1 ? "s" : ""} late</span>
                              <span style={{ margin: "0 8px", color: "var(--text-muted)" }}>|</span>
                              <span>Original score: <strong>{r.original_score}</strong></span>
                              <span style={{ margin: "0 8px", color: "var(--text-muted)" }}>|</span>
                              <span>Penalty: <strong style={{ color: "#f87171" }}>-{r.late_penalty.penalty_applied}</strong></span>
                            </div>
                            <button
                              className="btn"
                              onClick={() => {
                                updateGrade(reviewModal.index, "score", r.original_score);
                                updateGrade(reviewModal.index, "late_penalty", null);
                                updateGrade(reviewModal.index, "penalty_overridden", true);
                                addToast("Late penalty removed", "success");
                              }}
                              style={{ fontSize: "0.8rem", padding: "5px 12px", background: "rgba(245,158,11,0.2)", border: "1px solid rgba(245,158,11,0.4)", color: "#f59e0b" }}
                            >
                              <Icon name="Undo2" size={14} style={{ marginRight: "6px" }} />
                              Remove Penalty
                            </button>
                          </div>
                        )}

                        {/* Section Scores (if available) */}
                        {r.section_scores && Object.keys(r.section_scores).length > 0 && (
                          <div style={{ marginBottom: "8px" }}>
                            <label className="label">Section Breakdown</label>
                            <div style={{ display: "flex", flexDirection: "column", gap: "6px", background: "var(--input-bg)", padding: "12px", borderRadius: "8px" }}>
                              {Object.entries(r.section_scores).map(([section, data]) => (
                                <div key={section} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem" }}>
                                  <span style={{ color: "var(--text-secondary)" }}>{section}</span>
                                  <span style={{ fontWeight: 600, color: data.earned === data.possible ? "#4ade80" : data.earned === 0 ? "#f87171" : "#fbbf24" }}>
                                    {data.earned}/{data.possible} pts
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div
                          style={{
                            flex: 1,
                            display: "flex",
                            flexDirection: "column",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "6px",
                            }}
                          >
                            <label className="label" style={{ margin: 0 }}>
                              Feedback
                            </label>
                            {r.feedback && r.feedback.includes("---") && (
                              <button
                                onClick={async () => {
                                  const parts = r.feedback.split("---");
                                  if (parts.length >= 2) {
                                    const englishPart = parts[0].trim();
                                    try {
                                      const result =
                                        await api.retranslateFeedback(
                                          englishPart,
                                          r.student_language || "spanish",
                                        );
                                      if (result.translation) {
                                        const newFeedback =
                                          englishPart +
                                          "\n\n---\n\n" +
                                          result.translation;
                                        updateGrade(
                                          reviewModal.index,
                                          "feedback",
                                          newFeedback,
                                        );
                                      } else if (result.error) {
                                        addToast(
                                          "Translation error: " + result.error,
                                          "error",
                                        );
                                      }
                                    } catch (err) {
                                      addToast(
                                        "Failed to translate: " + err.message,
                                        "error",
                                      );
                                    }
                                  }
                                }}
                                style={{
                                  background: "rgba(99,102,241,0.1)",
                                  border: "1px solid rgba(99,102,241,0.3)",
                                  borderRadius: "6px",
                                  padding: "4px 10px",
                                  fontSize: "0.75rem",
                                  color: "#6366f1",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="Languages" size={12} />
                                Re-translate
                              </button>
                            )}
                          </div>
                          <textarea
                            className="input"
                            value={r.feedback}
                            onChange={(e) =>
                              updateGrade(
                                reviewModal.index,
                                "feedback",
                                e.target.value,
                              )
                            }
                            style={{
                              flex: 1,
                              minHeight: "200px",
                              resize: "none",
                            }}
                          />
                        </div>

                        {/* AI Reasoning - Collapsible */}
                        <div style={{ marginTop: "4px" }}>
                          <button
                            onClick={() => setShowAIReasoning(!showAIReasoning)}
                            style={{
                              background: "none",
                              border: "1px solid var(--glass-border)",
                              borderRadius: "8px",
                              color: "var(--text-secondary)",
                              cursor: "pointer",
                              padding: "8px 14px",
                              fontSize: "0.85rem",
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              width: "100%",
                              transition: "all 0.2s",
                            }}
                          >
                            <span style={{
                              transform: showAIReasoning ? "rotate(90deg)" : "rotate(0deg)",
                              transition: "transform 0.2s",
                              display: "inline-block",
                            }}>&#9654;</span>
                            AI Reasoning
                          </button>
                          <AIReasoningPanel
                            open={showAIReasoning}
                            aiInput={r.ai_input}
                            aiResponse={r.ai_response}
                          />
                        </div>
                      </div>
  );
}
