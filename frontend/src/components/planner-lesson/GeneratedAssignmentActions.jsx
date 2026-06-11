import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function GeneratedAssignmentActions(props) {
  const { addToast, assignment, config, editMode, generatedAssignment, previewShowAnswers, setActiveTab, setAssignment, setEditMode, setEditingQuestion, setGeneratedAssignment, setLoadedAssignmentName, setPreviewShowAnswers, setSelectedQuestions } = props;
  return (
                                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "docx",
                                            false,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as DOCX!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} />
                                    Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            false,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} />
                                    Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            true,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Answer key exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} />
                                    Answer Key
                                  </button>
                                  <button
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} />
                                    {previewShowAnswers ? " Hide Answers" : " Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      // Build answer key as grading notes
                                      let gradingNotes = "ANSWER KEY for " + generatedAssignment.title + "\n\n";
                                      (generatedAssignment.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (generatedAssignment.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        generatedAssignment.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }

                                      // Map sections to customMarkers, normalized so markers + effort = 100
                                      const effortPts = assignment.effortPoints ?? 15;
                                      const rawMarkers = (generatedAssignment.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      const rawTotal = rawMarkers.reduce((sum, m) => sum + m.points, 0);
                                      const available = 100 - effortPts;
                                      const markers = rawTotal > 0 && rawTotal !== available
                                        ? rawMarkers.map((m) => ({
                                            ...m,
                                            points: Math.round((m.points / rawTotal) * available),
                                          }))
                                        : rawMarkers;
                                      // Fix rounding drift so total is exactly 100
                                      const markerSum = markers.reduce((s, m) => s + m.points, 0);
                                      if (markers.length > 0 && markerSum !== available) {
                                        markers[0].points += available - markerSum;
                                      }

                                      setAssignment({
                                        ...assignment,
                                        title: generatedAssignment.title || "",
                                        totalPoints: generatedAssignment.total_points || 100,
                                        customMarkers: markers,
                                        effortPoints: effortPts,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{
                                      padding: "8px 14px",
                                      background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                    }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} />
                                    Set Up Grading
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} />
                                    {editMode ? " Exit Edit" : " Edit Questions"}
                                  </button>
                                  <button
                                    onClick={() => setGeneratedAssignment(null)}
                                    className="btn btn-secondary"
                                    style={{ padding: "6px 12px" }}
                                  >
                                    <Icon name="X" size={16} />
                                  </button>
                                </div>
  );
}
