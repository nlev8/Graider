import * as api from "../services/api";
import { checkRequirementsMismatch } from "../utils/standardsMismatch";

/*
 * useAssessmentAuthoring — the Planner assessment-authoring handlers (generate,
 * redistribute points, export to .docx, export for an LMS platform), pushed down from
 * the App.jsx shell (App.jsx decomposition slice 9). This is a FACTORY hook: it defines
 * handler closures and returns them, using NO internal React state/effects, so it imposes
 * no hook-order constraint and is simply called once during App's render. The handler
 * bodies moved VERBATIM; the App state values + setters they close over are passed in.
 * `api` and `checkRequirementsMismatch` were App-level imports and are imported here.
 */
export function useAssessmentAuthoring({
  config,
  addToast,
  selectedStandards,
  uploadedDocs,
  unitConfig,
  standards,
  assessmentConfig,
  selectedSources,
  globalAINotes,
  contentOnly,
  generatedAssessment,
  setAssessmentLoading,
  setGeneratedAssessment,
  setAssessmentAnswers,
}) {
  const generateAssessmentHandler = async () => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0 && uploadedDocs.length === 0) {
      addToast("Please select at least one standard or upload reference documents", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setAssessmentLoading(true);
    setGeneratedAssessment(null);
    try {
      // Get full standard objects
      const fullStandards = selectedStandards.map((code) => {
        return standards.find((s) => s.code === code) || { code, benchmark: code };
      });

      // Auto-generate title if not provided
      const title = assessmentConfig.title ||
        `${config.subject || "Subject"} ${assessmentConfig.type.charAt(0).toUpperCase() + assessmentConfig.type.slice(1)} - ${selectedStandards.slice(0, 2).join(", ")}${selectedStandards.length > 2 ? "..." : ""}`;

      // Merge uploaded docs into content sources
      const allSources = [...selectedSources];
      for (const doc of uploadedDocs) {
        allSources.push({ type: "document", content: { text: doc.text, filename: doc.filename } });
      }

      const data = await api.generateAssessment(
        fullStandards,
        {
          grade: config.grade_level,
          subject: config.subject,
          teacher_name: config.teacher_name,
          globalAINotes: globalAINotes,
          requirements: unitConfig.requirements || "",
          contentOnly: contentOnly,
        },
        { ...assessmentConfig, title, sectionCategories: Object.fromEntries(Object.entries(assessmentConfig.sectionCategories).map(function(e) { return [e[0], e[1] > 0]; })), questionTypeCounts: Object.fromEntries(Object.entries(assessmentConfig.sectionCategories).filter(function(e) { return e[1] > 0; })) },
        allSources
      );

      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else if (data.assessment) {
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        addToast("Assessment generated successfully!", "success");
        if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
      }
    } catch (e) {
      addToast("Error generating assessment: " + e.message, "error");
    } finally {
      setAssessmentLoading(false);
    }
  };

  const redistributePoints = (newTotal) => {
    if (!generatedAssessment) return;
    const currentTotal = generatedAssessment.total_points || 100;
    if (newTotal === currentTotal || newTotal < 1) return;

    const sections = (generatedAssessment.sections || []).map(s => {
      const questions = (s.questions || []).map(q => ({
        ...q,
        points: Math.max(1, Math.round((q.points || 1) * newTotal / currentTotal))
      }));
      return { ...s, questions, points: questions.reduce((sum, q) => sum + q.points, 0) };
    });

    const actualTotal = sections.reduce((sum, s) => sum + s.points, 0);
    if (actualTotal !== newTotal && sections.length > 0) {
      const lastSection = sections[sections.length - 1];
      if (lastSection.questions.length > 0) {
        const lastQ = lastSection.questions[lastSection.questions.length - 1];
        lastQ.points += (newTotal - actualTotal);
        lastSection.points += (newTotal - actualTotal);
      }
    }

    setGeneratedAssessment({ ...generatedAssessment, sections, total_points: newTotal });
  };

  const exportAssessmentHandler = async (includeAnswerKey = false) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessment(generatedAssessment, includeAnswerKey);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        // Download the document
        const link = document.createElement("a");
        link.href = "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64," + data.document;
        link.download = data.filename || "assessment.docx";
        link.click();
        addToast("Assessment exported!", "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  const exportAssessmentForPlatformHandler = async (platform) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessmentForPlatform(generatedAssessment, platform);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        const mimeTypes = {
          csv: "text/csv",
          xml: "application/xml",
          txt: "text/plain",
          json: "application/json",
        };
        const mimeType = mimeTypes[data.format] || data.mime_type || "application/octet-stream";
        const link = document.createElement("a");
        link.href = `data:${mimeType};base64,${data.document}`;
        link.download = data.filename;
        link.click();
        addToast(`Exported for ${platform}!`, "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  return {
    generateAssessmentHandler,
    redistributePoints,
    exportAssessmentHandler,
    exportAssessmentForPlatformHandler,
  };
}
