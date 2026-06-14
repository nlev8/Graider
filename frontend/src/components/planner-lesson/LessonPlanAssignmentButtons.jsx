import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function LessonPlanAssignmentButtons({ addToast, assignment, config, editMode, lessonPlan, previewShowAnswers, setActiveTab, setAssignment, setEditMode, setEditingQuestion, setLoadedAssignmentName, setPreviewShowAnswers, setSelectedQuestions }) {
  return (
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
  );
}
