import React from "react";
import Icon from "../Icon";
import QuestionEditOverlay from "../QuestionEditOverlay";
import QuestionAnswerInputs from "./QuestionAnswerInputs";

export default function AssessmentQuestionCard(props) {
  const { editMode, editingQuestion, q, qIdx, regenerateOneQuestion, regeneratingQuestions, sIdx, saveEditedQuestion, selectedQuestions, setEditingQuestion, toggleQuestionSelect } = props;
  // NOTE: the two inner key={qIdx} props below (qCard div, QuestionEditOverlay)
  // are intentionally-retained no-ops from the verbatim monolith split — the
  // real list key lives on <AssessmentQuestionCard key={qIdx}> at the .map()
  // boundary in AssessmentPreview.jsx. Safe to drop in a future cleanup.
                                    const qCard = (
                                    <div
                                      key={qIdx}
                                      style={{
                                        padding: "15px",
                                        background: "var(--glass-bg)",
                                        borderRadius: "10px",
                                        borderLeft: `4px solid ${
                                          q.dok === 1
                                            ? "#22c55e"
                                            : q.dok === 2
                                              ? "#3b82f6"
                                              : q.dok === 3
                                                ? "#f59e0b"
                                                : "#ef4444"
                                        }`,
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <span style={{ fontWeight: 700 }}>
                                          {q.number}. {q.question}
                                        </span>
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "8px",
                                            fontSize: "0.75rem",
                                            flexWrap: "wrap",
                                          }}
                                        >
                                          {q.type && (
                                            <span
                                              style={{
                                                padding: "2px 8px",
                                                borderRadius: "8px",
                                                background: "rgba(100, 116, 139, 0.15)",
                                                color: "#94a3b8",
                                                textTransform: "capitalize",
                                              }}
                                            >
                                              {q.type.replace(/_/g, " ")}
                                            </span>
                                          )}
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background: "rgba(139, 92, 246, 0.15)",
                                              color: "#8b5cf6",
                                            }}
                                          >
                                            {q.points} pt{q.points > 1 ? "s" : ""}
                                          </span>
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background:
                                                q.dok === 1
                                                  ? "rgba(34, 197, 94, 0.15)"
                                                  : q.dok === 2
                                                    ? "rgba(59, 130, 246, 0.15)"
                                                    : q.dok === 3
                                                      ? "rgba(245, 158, 11, 0.15)"
                                                      : "rgba(239, 68, 68, 0.15)",
                                              color:
                                                q.dok === 1
                                                  ? "#22c55e"
                                                  : q.dok === 2
                                                    ? "#3b82f6"
                                                    : q.dok === 3
                                                      ? "#f59e0b"
                                                      : "#ef4444",
                                            }}
                                          >
                                            DOK {q.dok}
                                          </span>
                                        </div>
                                      </div>
                                      {/* Quality warning badge */}
                                      {q.warning && (
                                        <div style={{
                                          padding: "6px 10px",
                                          background: q.warning_severity === "error" ? "rgba(239,68,68,0.15)" : q.warning_severity === "info" ? "rgba(59,130,246,0.15)" : "rgba(245,158,11,0.15)",
                                          border: q.warning_severity === "error" ? "1px solid rgba(239,68,68,0.3)" : q.warning_severity === "info" ? "1px solid rgba(59,130,246,0.3)" : "1px solid rgba(245,158,11,0.3)",
                                          borderRadius: "6px",
                                          fontSize: "0.8rem",
                                          color: q.warning_severity === "error" ? "#ef4444" : q.warning_severity === "info" ? "#3b82f6" : "#f59e0b",
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "6px",
                                          marginBottom: "8px",
                                        }}>
                                          <Icon name="AlertTriangle" size={14} />
                                          {q.warning}
                                        </div>
                                      )}
                                      {/* Answer inputs: multiple choice, true/false, matching, short answer, extended response */}
                                      <QuestionAnswerInputs {...props} />
                                      {q.standard && (
                                        <div
                                          style={{
                                            marginTop: "8px",
                                            fontSize: "0.8rem",
                                            color: "var(--text-muted)",
                                          }}
                                        >
                                          Standard: {q.standard}
                                        </div>
                                      )}
                                    </div>
                                    );
                                    return editMode ? (
                                      <QuestionEditOverlay
                                        key={qIdx}
                                        question={q}
                                        sectionIndex={sIdx}
                                        questionIndex={qIdx}
                                        isSelected={selectedQuestions.has(sIdx + "-" + qIdx)}
                                        isEditing={editingQuestion === sIdx + "-" + qIdx}
                                        isRegenerating={regeneratingQuestions.has(sIdx + "-" + qIdx)}
                                        onToggleSelect={toggleQuestionSelect}
                                        onStartEdit={setEditingQuestion}
                                        onSaveEdit={saveEditedQuestion}
                                        onCancelEdit={() => setEditingQuestion(null)}
                                        onRegenerateOne={regenerateOneQuestion}
                                      >
                                        {qCard}
                                      </QuestionEditOverlay>
                                    ) : qCard;
}
