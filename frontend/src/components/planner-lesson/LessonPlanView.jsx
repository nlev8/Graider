import React from "react";
import * as api from "../../services/api";
import AssignmentPlayer from "../AssignmentPlayer";
import QuestionEditToolbar from "../QuestionEditToolbar";
import LessonPlanActions from "./LessonPlanActions";
import ProjectPhasesView from "./ProjectPhasesView";
import LessonDaysView from "./LessonDaysView";
import GeneratedAssignmentPanel from "./GeneratedAssignmentPanel";

export default function LessonPlanView(props) {
  const { addToast, deleteSelectedQuestions, editMode, editingQuestion, getTotalQuestionCount, lessonPlan, previewResults, previewShowAnswers, regenerateOneQuestion, regenerateSelectedQuestions, regeneratingQuestions, saveEditedQuestion, selectAllQuestions, selectedQuestions, selectedStandards, setEditMode, setEditingQuestion, setPreviewResults, setSelectedQuestions, standards, toggleQuestionSelect } = props;
  return (
                        <div
                          className="glass-card"
                          style={{
                            padding: "30px",
                            maxHeight: "80vh",
                            overflowY: "auto",
                          }}
                        >
                          {/* Header */}
                          <div
                            style={{
                              marginBottom: "25px",
                              borderBottom: "1px solid var(--glass-border)",
                              paddingBottom: "20px",
                            }}
                          >
                            <h2
                              style={{
                                fontSize: "1.8rem",
                                fontWeight: 700,
                                marginBottom: "10px",
                              }}
                            >
                              {lessonPlan.title}
                            </h2>
                            <p
                              style={{
                                color: "var(--text-secondary)",
                                lineHeight: "1.6",
                                marginBottom: "20px",
                              }}
                            >
                              {lessonPlan.overview}
                            </p>
                            <LessonPlanActions {...props} />
                          </div>


                          {/* Standards aligned to this content */}
                          {selectedStandards.length > 0 && lessonPlan.sections && (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "12px" }}>
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

                          {/* Content display - varies by type */}
                          {lessonPlan.sections && !lessonPlan.days ? (
                            /* Assignment display - interactive AssignmentPlayer */
                            <>
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
                                assignment={lessonPlan}
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
                                    const published = await api.publishAssignment(lessonPlan);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />
                            </>
                          ) : lessonPlan.phases ? (
                            /* Project display - phases with tasks */
                            <ProjectPhasesView {...props} />
                          ) : (
                            /* Lesson Plan / Unit Plan display - days */
                            <LessonDaysView {...props} />
                          )}

                          {/* Generated Assignment Section */}
                          <GeneratedAssignmentPanel {...props} />
                        </div>
  );
}
