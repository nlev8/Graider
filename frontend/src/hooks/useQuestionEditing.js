import { useState } from "react";
import * as api from "../services/api";

export function useQuestionEditing({
  getActiveAssignment, setActiveAssignment,
  addToast, config, unitConfig, globalAINotes,
  standards, selectedStandards, uploadedDocs, setUploadedDocs,
}) {
  const [editMode, setEditMode] = useState(false);
  const [selectedQuestions, setSelectedQuestions] = useState(new Set());
  const [editingQuestion, setEditingQuestion] = useState(null); // "sIdx-qIdx" key
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());

  const toggleQuestionSelect = (qKey) => {
    setSelectedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(qKey)) next.delete(qKey);
      else next.add(qKey);
      return next;
    });
  };

  const selectAllQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const keys = new Set();
    a.sections.forEach((s, sIdx) => {
      (s.questions || []).forEach((_, qIdx) => keys.add(sIdx + "-" + qIdx));
    });
    setSelectedQuestions(keys);
  };

  const saveEditedQuestion = (sIdx, qIdx, updatedQuestion) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const copy = JSON.parse(JSON.stringify(a));
    if (copy.sections[sIdx]?.questions?.[qIdx]) {
      updatedQuestion.number = copy.sections[sIdx].questions[qIdx].number;
      copy.sections[sIdx].questions[qIdx] = updatedQuestion;
      copy.sections[sIdx].points = copy.sections[sIdx].questions.reduce(
        (sum, q) => sum + (q.points || 0), 0
      );
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);
      setActiveAssignment(copy);
    }
    setEditingQuestion(null);
    addToast("Question updated", "success");
  };

  const deleteSelectedQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;
    const copy = JSON.parse(JSON.stringify(a));
    const deleteCount = selectedQuestions.size;

    copy.sections.forEach((section, sIdx) => {
      section.questions = (section.questions || []).filter(
        (_, qIdx) => !selectedQuestions.has(sIdx + "-" + qIdx)
      );
      section.questions.forEach((q, i) => { q.number = i + 1; });
      section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
    });

    copy.sections = copy.sections.filter((s) => s.questions && s.questions.length > 0);
    copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

    setActiveAssignment(copy);
    setSelectedQuestions(new Set());
    addToast(deleteCount + " question(s) removed", "success");
  };

  const regenerateSelectedQuestions = async () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;

    const questionsToReplace = [];
    const existingQuestions = [];

    a.sections.forEach((section, sIdx) => {
      (section.questions || []).forEach((q, qIdx) => {
        const key = sIdx + "-" + qIdx;
        if (selectedQuestions.has(key)) {
          questionsToReplace.push({
            section_index: sIdx,
            question_index: qIdx,
            question_type: q.question_type || q.type || "short_answer",
            points: q.points || 1,
            dok: q.dok || 1,
            standard: q.standard || "",
          });
        } else {
          existingQuestions.push(q.question || "");
        }
      });
    });

    setRegeneratingQuestions(new Set(selectedQuestions));

    try {
      const data = await api.regenerateQuestions(
        questionsToReplace,
        existingQuestions,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });

      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setSelectedQuestions(new Set());

      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast(data.replacements.length + " question(s) regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

  const regenerateOneQuestion = async (sIdx, qIdx) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const q = a.sections[sIdx]?.questions?.[qIdx];
    if (!q) return;

    const key = sIdx + "-" + qIdx;
    setRegeneratingQuestions(new Set([key]));

    const existingTexts = [];
    a.sections.forEach((s) => {
      (s.questions || []).forEach((ques) => existingTexts.push(ques.question || ""));
    });

    try {
      const data = await api.regenerateQuestions(
        [{
          section_index: sIdx,
          question_index: qIdx,
          question_type: q.question_type || q.type || "short_answer",
          points: q.points || 1,
          dok: q.dok || 1,
          standard: q.standard || "",
        }],
        existingTexts,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });
      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, ques) => sum + (ques.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setEditingQuestion(null);
      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast("Question regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

  return {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  };
}
