import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

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
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "docx", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as DOCX!", "success");
                                        }
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
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as PDF!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", true, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Answer key exported as PDF!", "success");
                                        }
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
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} /> {previewShowAnswers ? "Hide Answers" : "Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      let gradingNotes = "ANSWER KEY for " + lessonPlan.title + "\n\n";
                                      (lessonPlan.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (lessonPlan.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        lessonPlan.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }
                                      const markers = (lessonPlan.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      setAssignment({
                                        ...assignment,
                                        title: lessonPlan.title || "",
                                        totalPoints: lessonPlan.total_points || 100,
                                        customMarkers: markers,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px", background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} /> Set Up Grading
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
