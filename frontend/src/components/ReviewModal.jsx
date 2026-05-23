import React from "react";
import Icon from "./Icon";
import AIReasoningPanel from "./AIReasoningPanel";
import * as api from "../services/api";

export default function ReviewModal({ addToast, autoApproveEmails, config, editedEmails, editedResults, emailApprovals, reviewModal, reviewModalRightTab, reviewModalTab, sentEmails, setEditedEmails, setReviewModal, setReviewModalRightTab, setReviewModalTab, setSentEmails, setShowAIReasoning, setStatus, showAIReasoning, status, updateApprovalStatus, updateGrade }) {
  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-content-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "20px 30px",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0 }}>
                Review:{" "}
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.student_name
                }
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "4px 0 0 0" }}>
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.assignment ||
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.filename
                }
              </p>
            </div>
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              style={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "8px",
                color: "var(--text-secondary)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--glass-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--glass-bg)")
              }
            >
              <Icon name="X" size={20} />
            </button>
          </div>
          <div style={{ flex: 1, overflow: "hidden", padding: "25px 30px" }}>
            {(() => {
              const r =
                editedResults[reviewModal.index] ||
                status.results[reviewModal.index];
              if (!r) return null;
              return (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "30px",
                    height: "100%",
                  }}
                >
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
                        <div
                          style={{
                            height: "100%",
                            background: "var(--input-bg)",
                            padding: "20px",
                            borderRadius: "10px",
                            overflowY: "auto",
                          }}
                        >
                          {(() => {
                            const imageExts = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];
                            const fname = (r.filename || '').toLowerCase();
                            const isImage = r.is_handwritten || imageExts.some(ext => fname.endsWith(ext)) || r.student_content === '[Image file]';
                            if (isImage) {
                              const imagePath = r.filepath || r.original_image_path;
                              return (
                                <div style={{ textAlign: "center" }}>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      gap: "8px",
                                      marginBottom: "15px",
                                      color: "#10b981",
                                      fontWeight: 500,
                                    }}
                                  >
                                    <Icon name={r.is_handwritten ? "PenTool" : "Image"} size={18} />
                                    {r.is_handwritten ? "Handwritten Assignment" : "Image Submission"}
                                  </div>
                                  {imagePath ? (
                                    <img
                                      src={"/api/serve-file?path=" + encodeURIComponent(imagePath)}
                                      alt={r.filename || "Student submission"}
                                      style={{
                                        maxWidth: "100%",
                                        borderRadius: "10px",
                                        boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
                                      }}
                                    />
                                  ) : (
                                    <p
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-muted)",
                                      }}
                                    >
                                      {r.is_handwritten
                                        ? "Handwritten responses were extracted by AI vision. Check the \"Responses\" tab to see extracted answers."
                                        : "[No image path available - click Open Original to view]"}
                                    </p>
                                  )}
                                </div>
                              );
                            }
                            return (
                              <div
                                style={{
                                  whiteSpace: "pre-wrap",
                                  fontSize: "22px",
                                  lineHeight: 1.7,
                                  color: "var(--text-secondary)",
                                  fontFamily: "monospace",
                                }}
                              >
                                {r.full_content ||
                                  r.student_content ||
                                  "[No content - click Open Original to view]"}
                              </div>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  </div>
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
                    {/* Right Panel Header with Tabs */}
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
                          onClick={() => setReviewModalRightTab("edit")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "edit"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "edit"
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
                          <Icon name="Award" size={14} />
                          Grade & Feedback
                        </button>
                        <button
                          onClick={() => setReviewModalRightTab("email")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "email"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "email"
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
                          <Icon name="Mail" size={14} />
                          Email Preview
                        </button>
                      </div>
                    </div>

                    {/* Right Panel Content */}
                    {reviewModalRightTab === "edit" ? (
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
                    ) : (
                      <div
                        style={{ flex: 1, padding: "20px", overflow: "auto" }}
                      >
                        <div
                          style={{
                            background: "#fff",
                            borderRadius: "12px",
                            padding: "30px",
                            color: "#333",
                            fontFamily: "Georgia, serif",
                            lineHeight: 1.7,
                            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: "20px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid #eee",
                            }}
                          >
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <span>To:</span>
                              <input
                                type="email"
                                value={editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email ?? ""}
                                onChange={(e) => {
                                  const newEmail = e.target.value;
                                  const studentId = r.student_id;
                                  const studentName = r.student_name;

                                  // Update editedEmails for ALL results with the same student
                                  setEditedEmails((prev) => {
                                    const updated = { ...prev };
                                    status.results.forEach((result, idx) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        updated[idx] = {
                                          ...prev[idx],
                                          email: newEmail,
                                        };
                                      }
                                    });
                                    return updated;
                                  });

                                  // Also update status.results so it persists when saved
                                  setStatus((prev) => ({
                                    ...prev,
                                    results: prev.results.map((result) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        return { ...result, student_email: newEmail };
                                      }
                                      return result;
                                    }),
                                  }));
                                }}
                                placeholder="Enter student email..."
                                style={{
                                  flex: 1,
                                  padding: "4px 8px",
                                  border: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "1px solid #ddd" : "1px solid #f87171",
                                  borderRadius: "4px",
                                  fontSize: "0.85rem",
                                  background: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "#fff" : "#fef2f2",
                                }}
                              />
                              {!(r.student_email || r.email) && !editedEmails[reviewModal.index]?.email && (
                                <span style={{ color: "#f87171", fontSize: "0.75rem" }}>
                                  (not found)
                                </span>
                              )}
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                              }}
                            >
                              Subject: {r.assignment || "Assignment"} - Grade:{" "}
                              {r.letter_grade} ({r.score}%)
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Dear{" "}
                              {r.first_name ||
                                r.student_name?.split(" ")[0] ||
                                "Student"}
                              ,
                            </p>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Your assignment{" "}
                              <strong>{r.assignment || "Assignment"}</strong>{" "}
                              has been graded.
                            </p>
                            <div
                              style={{
                                background:
                                  r.score >= 90
                                    ? "#dcfce7"
                                    : r.score >= 80
                                      ? "#dbeafe"
                                      : r.score >= 70
                                        ? "#fef3c7"
                                        : "#fee2e2",
                                padding: "15px 20px",
                                borderRadius: "8px",
                                marginBottom: "20px",
                                textAlign: "center",
                              }}
                            >
                              <div
                                style={{
                                  fontSize: "2rem",
                                  fontWeight: 700,
                                  color:
                                    r.score >= 90
                                      ? "#16a34a"
                                      : r.score >= 80
                                        ? "#2563eb"
                                        : r.score >= 70
                                          ? "#d97706"
                                          : "#dc2626",
                                }}
                              >
                                {r.letter_grade}
                              </div>
                              <div style={{ fontSize: "1rem", color: "#666" }}>
                                {r.score} / 100
                              </div>
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <h4
                              style={{
                                margin: "0 0 10px 0",
                                fontSize: "1rem",
                                color: "#333",
                              }}
                            >
                              Feedback:
                            </h4>
                            <div
                              style={{ whiteSpace: "pre-wrap", color: "#444" }}
                            >
                              {r.feedback || "(No feedback provided)"}
                            </div>
                          </div>
                          <p
                            style={{
                              margin: "20px 0 0 0",
                              color: "#666",
                              fontSize: "0.9rem",
                            }}
                          >
                            If you have any questions about your grade, please
                            see me during class or office hours.
                          </p>
                          <div style={{ margin: "15px 0 0 0", color: "#666", whiteSpace: "pre-wrap" }}>
                            {config.email_signature ? (
                              config.email_signature
                            ) : (
                              <>
                                Best regards,
                                <br />
                                <strong>
                                  {config.teacher_name || "Your Teacher"}
                                </strong>
                                {config.school_name && (
                                  <>
                                    <br />
                                    <span>{config.school_name}</span>
                                  </>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                        {/* Approve/Reject Buttons */}
                        {!autoApproveEmails && (
                          <div
                            style={{
                              marginTop: "20px",
                              display: "flex",
                              gap: "10px",
                              justifyContent: "center",
                            }}
                          >
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                addToast(
                                  "Email approved for sending",
                                  "success",
                                );
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "linear-gradient(135deg, #22c55e, #16a34a)"
                                    : "rgba(74,222,128,0.15)",
                                border:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "none"
                                    : "1px solid rgba(74,222,128,0.3)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "#fff"
                                    : "#4ade80",
                              }}
                            >
                              <Icon name="Check" size={18} />
                              {emailApprovals[reviewModal.index] === "approved"
                                ? "Approved"
                                : "Approve Email"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "rejected");
                                addToast("Email marked as rejected", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "rgba(248,113,113,0.2)"
                                    : "var(--glass-bg)",
                                border: "1px solid var(--glass-border)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "#f87171"
                                    : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="X" size={18} />
                              {emailApprovals[reviewModal.index] === "rejected"
                                ? "Rejected"
                                : "Reject"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                setSentEmails((prev) => ({
                                  ...prev,
                                  [reviewModal.index]: true,
                                }));
                                addToast("Marked as sent (no email sent)", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background: sentEmails[reviewModal.index]
                                  ? "rgba(59,130,246,0.25)"
                                  : "var(--glass-bg)",
                                border: sentEmails[reviewModal.index]
                                  ? "1px solid rgba(59,130,246,0.4)"
                                  : "1px solid var(--glass-border)",
                                color: sentEmails[reviewModal.index]
                                  ? "#3b82f6"
                                  : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="Send" size={18} />
                              {sentEmails[reviewModal.index]
                                ? "Sent"
                                : "Mark as Sent"}
                            </button>
                          </div>
                        )}
                        <p
                          style={{
                            marginTop: "15px",
                            fontSize: "0.8rem",
                            color: "var(--text-muted)",
                            textAlign: "center",
                          }}
                        >
                          <Icon
                            name="Info"
                            size={12}
                            style={{
                              marginRight: "4px",
                              verticalAlign: "middle",
                            }}
                          />
                          Editing feedback in "Grade & Feedback" tab updates
                          this preview automatically
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
          <div
            style={{
              padding: "20px 30px",
              borderTop: "1px solid var(--glass-border)",
              display: "flex",
              gap: "12px",
              justifyContent: "flex-end",
            }}
          >
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              className="btn btn-primary"
              style={{ padding: "10px 24px" }}
            >
              Done
            </button>
          </div>
        </div>
  );
}
