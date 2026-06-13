import * as api from "../services/api";
import { getMarkerText, getEndMarker } from "../utils/markerHelpers";
import { highlightTextInHtml, textToRichHtml } from "../utils/htmlHighlight";
import { HIGHLIGHT_COLORS, markerLibrary } from "./appConstants";
import { useDocImport } from "../hooks/useDocImport";
import { useMarkerEditing } from "../hooks/useMarkerEditing";
import { useAssignmentBuilderActions } from "../hooks/useAssignmentBuilderActions";

/*
 * useAppBuilderHandlers — segment 6 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 1440-1673: grading start/stop
 * handlers, getDefaultEmailBody, handleGenerateModelAnswers, setEndMarker
 * (pre-existing dead code, moved as-is — deleting is cleanup, not a move),
 * applyAllHighlights, useDocImport (which must stay AFTER applyAllHighlights —
 * the slice-15 TDZ lesson), useMarkerEditing, the question CRUD trio, and
 * useAssignmentBuilderActions.
 *
 * KNOWN PRE-EXISTING BUG, preserved verbatim: handleStopGrading calls
 * setAutoGrade(false) but no such binding exists anywhere (pre-split App.jsx
 * 1451 had the same free identifier). The ReferenceError it throws at click
 * time is swallowed by the surrounding try/catch, so behavior is unchanged.
 * Flagged as a follow-up in the finale PR rather than fixed here (Class A).
 * See useAppCoreState for the hook-order contract.
 */
export function useAppBuilderHandlers(ctx) {
  const {
    addToast, assignment, config, docEditorModal, docHtmlRef, highlighterMode, importedDoc,
    loadedAssignmentName, savedAssignments, setAssignment, setDocEditorModal, setImportedDoc,
    setIsLoadingAssignment, setLoadedAssignmentName, setModelAnswersLoading,
    setSavedAssignmentData, setSavedAssignments, skipAutoSaveRef, status,
  } = ctx;

  // Grading functions
  const handleStartGrading = async () => {
    // Folder-based bulk grading removed — grading happens via portal submissions.
    // This function is kept as a stub for UI references.
    addToast("Grading happens automatically when students submit via the portal.", "info");
  };


  const handleStopGrading = async () => {
    try {
      await api.stopGrading();
      setAutoGrade(false);
    } catch (error) {
      console.error("Failed to stop grading:", error);
    }
  };

  // handleIndividualFileSelect, handleIndividualGrade, clearIndividualUpload,
  // getStudentSuggestions all moved into tabs/GradeTab.jsx (with the state they
  // close over) in PR 3 of the Grade tab extraction sprint.

  // Generate default email body for a result (matches exactly what backend sends)
  const getDefaultEmailBody = (index) => {
    const r = status.results[index];
    if (!r) return "";
    const firstName = r.student_name?.split(" ")[0] || "Student";
    const signature = [
      config.teacher_name || "Your Teacher",
      config.subject,
      config.school_name,
    ]
      .filter(Boolean)
      .join("\n");

    return `Hi ${firstName},

Here is your grade and feedback for ${r.assignment || "your assignment"}:

${"=".repeat(40)}
GRADE: ${r.score}/100 (${r.letter_grade})
${"=".repeat(40)}

FEEDBACK:
${r.feedback || "No feedback available."}

${"=".repeat(40)}

If you have any questions, please see me during class.

${signature}`;
  };

  // Builder functions

  // Helper to get marker text (handles both string and object formats)
  // Marker-accessor helpers extracted to utils/markerHelpers.js (decomp slice 14).


  const handleGenerateModelAnswers = async () => {
    const docText = importedDoc.text || (importedDoc.html ? importedDoc.html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() : '');
    if (!importedDoc || !docText) {
      addToast("Import the assignment document first", "warning");
      return;
    }
    if (!assignment.customMarkers || assignment.customMarkers.length === 0) {
      addToast("Add section markers first", "warning");
      return;
    }
    setModelAnswersLoading(true);
    try {
      var settingsResp = {};
      try { settingsResp = await api.loadGlobalSettings(); } catch(e) {}
      var settings = (settingsResp && settingsResp.settings) || {};
      var data = await api.generateModelAnswers({
        customMarkers: assignment.customMarkers,
        documentText: docText,
        title: assignment.title,
        grade_level: config.grade_level || "7",
        subject: config.subject || "Social Studies",
        globalAINotes: settings.globalAINotes || ""
      });
      if (data.error) { addToast(data.error, "error"); return; }
      var answers = {};
      (data.model_answers || []).forEach(function(ma) {
        answers[ma.section] = ma.answer;
      });
      setAssignment(function(prev) { return Object.assign({}, prev, { modelAnswers: answers }); });
      addToast("Model answers generated! Review and edit below.", "success");
    } catch (err) {
      addToast("Failed: " + err.message, "error");
    } finally {
      setModelAnswersLoading(false);
    }
  };



  // Add or update end marker for a given start marker
  const setEndMarker = (markerIndex, endText) => {
    const updated = [...(assignment.customMarkers || [])];
    const current = updated[markerIndex];
    const startText = getMarkerText(current);

    if (endText && endText.trim()) {
      // Convert to object with end marker
      updated[markerIndex] = { start: startText, end: endText.trim() };
    } else {
      // Remove end marker, convert back to string
      updated[markerIndex] = startText;
    }
    setAssignment({ ...assignment, customMarkers: updated });
  };

  // Normalize special characters (smart quotes, em-dashes) to ASCII equivalents
  // HTML/text highlight helpers extracted to utils/htmlHighlight.js (decomp slice 13).


  // Apply all marker highlights to HTML (start, end, AND exclude markers)
  const applyAllHighlights = (html, markers, excludeMarkers) => {
    if (!html) return html;

    let result = html;
    if (markers) {
      markers.forEach((marker, i) => {
        const startText = getMarkerText(marker);
        const endText = getEndMarker(marker);

        // Highlight start marker in green
        result = highlightTextInHtml(result, startText, HIGHLIGHT_COLORS.start, `start-${i}`);

        // Highlight end marker in red (if exists)
        if (endText) {
          result = highlightTextInHtml(result, endText, HIGHLIGHT_COLORS.end, `end-${i}`);
        }
      });
    }

    // Re-apply exclude marker highlights (orange)
    if (excludeMarkers) {
      excludeMarkers.forEach((marker, i) => {
        result = highlightTextInHtml(result, marker, HIGHLIGHT_COLORS.exclude, `exclude-${i}`);
      });
    }
    return result;
  };

  // Doc import + editor-open handlers extracted to useDocImport (decomp slice 16).
  // Placed AFTER applyAllHighlights: handleDocImport closes over it, and this factory call
  // runs during render, so the const must be initialized first (slice-15 TDZ lesson).
  const {
    handleDocImport,
    openDocEditor,
  } = useDocImport({
  importedDoc,
  assignment,
  savedAssignments,
  applyAllHighlights,
  addToast,
  setImportedDoc,
  setAssignment,
  setLoadedAssignmentName,
  setDocEditorModal,
  });

  // Doc-editor marker handlers extracted to useMarkerEditing (decomp slice 15).
  const {
    addSelectedAsMarker,
    removeMarker,
  } = useMarkerEditing({
  docHtmlRef,
  highlighterMode,
  assignment,
  docEditorModal,
  importedDoc,
  HIGHLIGHT_COLORS,
  applyAllHighlights,
  addToast,
  setAssignment,
  setDocEditorModal,
  setImportedDoc,
  });

  const addQuestion = () => {
    setAssignment({
      ...assignment,
      questions: [
        ...assignment.questions,
        {
          id: Date.now(),
          type: "short_answer",
          prompt: "",
          points: 10,
          marker: markerLibrary[assignment.subject]?.[0] || "Answer:",
        },
      ],
    });
  };

  const updateQuestion = (index, field, value) => {
    const updated = [...assignment.questions];
    updated[index] = { ...updated[index], [field]: value };
    setAssignment({ ...assignment, questions: updated });
  };

  const removeQuestion = (index) => {
    setAssignment({
      ...assignment,
      questions: assignment.questions.filter((_, i) => i !== index),
    });
  };

  // Assignment-builder CRUD handlers extracted to useAssignmentBuilderActions (decomp slice 10).
  const {
    saveAssignmentConfig,
    loadAssignment,
    deleteAssignment,
    exportAssignment,
  } = useAssignmentBuilderActions({
  assignment,
  savedAssignments,
  loadedAssignmentName,
  docEditorModal,
  importedDoc,
  skipAutoSaveRef,
  textToRichHtml,
  addToast,
  setAssignment,
  setImportedDoc,
  setDocEditorModal,
  setLoadedAssignmentName,
  setSavedAssignments,
  setSavedAssignmentData,
  setIsLoadingAssignment,
  });

  return {
    handleStartGrading, handleStopGrading, getDefaultEmailBody, handleGenerateModelAnswers,
    setEndMarker, applyAllHighlights, handleDocImport, openDocEditor, addSelectedAsMarker,
    removeMarker, addQuestion, updateQuestion, removeQuestion, saveAssignmentConfig,
    loadAssignment, deleteAssignment, exportAssignment,
  };
}
