import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import LessonPlanAssignmentButtons from "./LessonPlanAssignmentButtons";

export default function LessonPlanActions(props) {
  const { addToast, assignment, config, editMode, exportLessonPlanHandler, generatedAssignment, lessonPlan, previewShowAnswers, publishAssessmentHandler, publishingAssessment, setActiveTab, setAssignment, setBrainstormIdeas, setEditMode, setEditingQuestion, setGeneratedAssignment, setLessonPlan, setLoadedAssignmentName, setPlannerMode, setPreviewShowAnswers, setSelectedIdea, setSelectedQuestions, setShowSaveLesson } = props;
  return (
                            <div
                              style={{
                                display: "flex",
                                gap: "10px",
                                alignItems: "center",
                                flexWrap: "wrap",
                              }}
                            >
                              {lessonPlan.sections && !lessonPlan.days ? (
                                /* Assignment-type content: Export PDF, Answer Key, Interactive Preview, Set Up Grading */
                                <LessonPlanAssignmentButtons
                                  addToast={addToast}
                                  assignment={assignment}
                                  config={config}
                                  editMode={editMode}
                                  lessonPlan={lessonPlan}
                                  previewShowAnswers={previewShowAnswers}
                                  setActiveTab={setActiveTab}
                                  setAssignment={setAssignment}
                                  setEditMode={setEditMode}
                                  setEditingQuestion={setEditingQuestion}
                                  setLoadedAssignmentName={setLoadedAssignmentName}
                                  setPreviewShowAnswers={setPreviewShowAnswers}
                                  setSelectedQuestions={setSelectedQuestions}
                                />
                              ) : generatedAssignment ? (
                                /* Assignment was created from this lesson — export it as PDF */
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "docx", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as DOCX!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} /> Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export assignment as PDF with graphics"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", true, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Answer key exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} /> Answer Key
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} /> {editMode ? "Exit Edit" : "Edit Questions"}
                                  </button>
                                </>
                              ) : (
                                /* Lesson plan / project: standard Export + Save */
                                <>
                                  <button
                                    onClick={exportLessonPlanHandler}
                                    className="btn btn-secondary"
                                  >
                                    <Icon name="Download" size={16} /> Export
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => setShowSaveLesson(true)}
                                className="btn btn-secondary"
                                title="Save for use in assessment generation"
                              >
                                <Icon name="FolderPlus" size={16} /> Save to Unit
                              </button>
                              <button
                                onClick={() => { setPlannerMode("tools"); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 14px", background: "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(8,145,178,0.15))", border: "1px solid rgba(6,182,212,0.3)" }}
                                title="Generate study guide from this content"
                              >
                                <Icon name="BookOpen" size={16} /> Study Guide
                              </button>
                              {(lessonPlan.sections || generatedAssignment) && !lessonPlan.phases && (
                                <button
                                  onClick={publishAssessmentHandler}
                                  disabled={publishingAssessment}
                                  className="btn"
                                  style={{ padding: "8px 16px", background: "linear-gradient(135deg, #8b5cf6, #6366f1)" }}
                                >
                                  <Icon name={publishingAssessment ? "Loader" : "Share2"} size={16} />
                                  {publishingAssessment ? "Publishing..." : "Publish to Portal"}
                                </button>
                              )}
                              {/* Assignment/Essay/Project creation is handled via the Details sidebar Content Type selector */}
                              <div style={{ flex: 1 }} />
                              <button
                                onClick={() => {
                                  setLessonPlan(null);
                                  setSelectedIdea(null);
                                  setBrainstormIdeas([]);
                                  setGeneratedAssignment(null);
                                }}
                                className="btn btn-secondary"
                              >
                                Close
                              </button>
                            </div>
  );
}
