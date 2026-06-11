import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import AssignmentPlayer from "../AssignmentPlayer";
import QuestionEditToolbar from "../QuestionEditToolbar";
import GeneratedAssignmentActions from "./GeneratedAssignmentActions";

export default function GeneratedAssignmentPanel(props) {
  const { addToast, deleteSelectedQuestions, editMode, editingQuestion, generatedAssignment, getTotalQuestionCount, previewResults, previewShowAnswers, regenerateOneQuestion, regenerateSelectedQuestions, regeneratingQuestions, saveEditedQuestion, selectAllQuestions, selectedQuestions, selectedStandards, setEditMode, setEditingQuestion, setPreviewResults, setSelectedQuestions, standards, toggleQuestionSelect } = props;
  if (!generatedAssignment) return null;
  return (
                            <div
                              style={{
                                marginTop: "30px",
                                padding: "25px",
                                background:
                                  "linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,182,212,0.1))",
                                borderRadius: "16px",
                                border: "1px solid rgba(16,185,129,0.3)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "flex-start",
                                  marginBottom: "20px",
                                }}
                              >
                                <div>
                                  <h3
                                    style={{
                                      fontSize: "1.4rem",
                                      fontWeight: 700,
                                      marginBottom: "8px",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "10px",
                                    }}
                                  >
                                    <Icon
                                      name="FileText"
                                      size={24}
                                      style={{ color: "#10b981" }}
                                    />
                                    {generatedAssignment.title}
                                  </h3>
                                  <div
                                    style={{
                                      display: "flex",
                                      gap: "10px",
                                      flexWrap: "wrap",
                                    }}
                                  >
                                    <span
                                      style={{
                                        padding: "4px 10px",
                                        background: "rgba(16,185,129,0.2)",
                                        color: "#10b981",
                                        borderRadius: "12px",
                                        fontSize: "0.8rem",
                                        fontWeight: 500,
                                      }}
                                    >
                                      {generatedAssignment.type
                                        ?.charAt(0)
                                        .toUpperCase() +
                                        generatedAssignment.type?.slice(1)}
                                    </span>
                                    {generatedAssignment.time_estimate && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(99,102,241,0.2)",
                                          color: "#818cf8",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        <Icon
                                          name="Clock"
                                          size={12}
                                          style={{ marginRight: "4px" }}
                                        />
                                        {generatedAssignment.time_estimate}
                                      </span>
                                    )}
                                    {generatedAssignment.total_points && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(251,191,36,0.2)",
                                          color: "#fbbf24",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        {generatedAssignment.total_points}{" "}
                                        points
                                      </span>
                                    )}
                                  </div>
                                  {selectedStandards.length > 0 && (
                                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                                      {selectedStandards.map((code) => {
                                        const std = standards.find((s) => s.code === code);
                                        return (
                                          <span
                                            key={code}
                                            title={std?.benchmark || code}
                                            style={{
                                              padding: "3px 8px",
                                              background: "rgba(139,92,246,0.15)",
                                              color: "#a78bfa",
                                              borderRadius: "8px",
                                              fontSize: "0.75rem",
                                              fontWeight: 500,
                                              maxWidth: "280px",
                                              overflow: "hidden",
                                              textOverflow: "ellipsis",
                                              whiteSpace: "nowrap",
                                            }}
                                          >
                                            {code}{std?.benchmark ? ": " + std.benchmark : ""}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                                <GeneratedAssignmentActions {...props} />
                              </div>

                              {editMode && (
                                <QuestionEditToolbar
                                  selectedCount={selectedQuestions.size}
                                  totalCount={getTotalQuestionCount()}
                                  onSelectAll={selectAllQuestions}
                                  onDeselectAll={() => setSelectedQuestions(new Set())}
                                  onDeleteSelected={deleteSelectedQuestions}
                                  onRegenerateSelected={regenerateSelectedQuestions}
                                  onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  isRegenerating={regeneratingQuestions.size > 0}
                                />
                              )}
                              <AssignmentPlayer
                                assignment={generatedAssignment}
                                showAnswers={previewShowAnswers}
                                results={previewResults}
                                editMode={editMode}
                                selectedQuestions={selectedQuestions}
                                editingQuestion={editingQuestion}
                                regeneratingQuestions={regeneratingQuestions}
                                onToggleSelect={toggleQuestionSelect}
                                onStartEdit={setEditingQuestion}
                                onSaveEdit={saveEditedQuestion}
                                onCancelEdit={() => setEditingQuestion(null)}
                                onRegenerateOne={regenerateOneQuestion}
                                onSubmit={async (answers) => {
                                  try {
                                    const published = await api.publishAssignment(generatedAssignment);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />

                              {/* Rubric */}
                              {generatedAssignment.rubric?.criteria && (
                                <div
                                  style={{
                                    padding: "15px",
                                    background: "rgba(251,191,36,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(251,191,36,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#fbbf24",
                                      marginBottom: "10px",
                                      fontWeight: 600,
                                    }}
                                  >
                                    <Icon
                                      name="Award"
                                      size={14}
                                      style={{ marginRight: "6px" }}
                                    />
                                    Grading Rubric
                                  </h4>
                                  {generatedAssignment.rubric.criteria.map(
                                    (c, cIdx) => (
                                      <div
                                        key={cIdx}
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          padding: "8px 0",
                                          borderBottom:
                                            cIdx <
                                            generatedAssignment.rubric.criteria
                                              .length -
                                              1
                                              ? "1px solid rgba(251,191,36,0.2)"
                                              : "none",
                                        }}
                                      >
                                        <span style={{ fontWeight: 500 }}>
                                          {c.name}
                                        </span>
                                        <span
                                          style={{
                                            color: "var(--text-secondary)",
                                            fontSize: "0.9rem",
                                          }}
                                        >
                                          {c.points} pts - {c.description}
                                        </span>
                                      </div>
                                    ),
                                  )}
                                </div>
                              )}
                            </div>
  );
}
