import * as api from "../services/api";

/*
 * useSavedAssessmentActions — the saved-assessment / saved-lesson content handlers, pushed
 * down from the App.jsx shell (App.jsx decomposition slice 17). FACTORY hook (no internal
 * React state/effects → no hook-order constraint). saveAssessmentHandler + deleteSavedAssessment
 * call the sibling fetchSavedAssessments (internal cross-calls, resolve in-factory). Bodies
 * moved VERBATIM; the 13 App state values/setters they close over are passed in; api is
 * imported here (also stays imported in App).
 */
export function useSavedAssessmentActions({
  generatedAssessment,
  saveAssessmentName,
  assessmentAnswers,
  addToast,
  setSavingAssessment,
  setSaveAssessmentName,
  setSavedLessons,
  setLoadingSavedAssessments,
  setSavedAssessments,
  setGeneratedAssessment,
  setAssessmentAnswers,
  setAssessmentGradingResults,
  setGradingAssessment,
}) {
  // Save assessment locally for later use (makeup exams)
  const saveAssessmentHandler = async () => {
    if (!generatedAssessment) {
      addToast("No assessment to save", "warning");
      return;
    }
    if (!saveAssessmentName.trim()) {
      addToast("Please enter a name for the assessment", "warning");
      return;
    }
    setSavingAssessment(true);
    try {
      const data = await api.saveAssessmentLocally(generatedAssessment, saveAssessmentName.trim());
      if (data.error) {
        addToast("Error saving: " + data.error, "error");
      } else if (data.success) {
        addToast("Assessment saved successfully!", "success");
        setSaveAssessmentName('');
        // Refresh saved assessments list
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error saving assessment: " + e.message, "error");
    } finally {
      setSavingAssessment(false);
    }
  };

  // Fetch saved lessons for assessment content sources
  const fetchSavedLessons = async () => {
    try {
      const data = await api.listLessons();
      if (data.units) {
        setSavedLessons(data);
      }
    } catch (e) {
      console.error("Error loading saved lessons:", e);
    }
  };

  // Fetch saved assessments
  const fetchSavedAssessments = async () => {
    setLoadingSavedAssessments(true);
    try {
      const data = await api.listSavedAssessments();
      if (data.assessments) {
        setSavedAssessments(data.assessments);
      }
    } catch (e) {
      console.error("Error loading saved assessments:", e);
    } finally {
      setLoadingSavedAssessments(false);
    }
  };

  // Load a saved assessment
  const loadSavedAssessment = async (filename) => {
    try {
      const data = await api.loadSavedAssessment(filename);
      if (data.error) {
        addToast("Error loading assessment: " + data.error, "error");
      } else if (data.assessment) {
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({});
        setAssessmentGradingResults(null);
        addToast("Assessment loaded!", "success");
      }
    } catch (e) {
      addToast("Error loading assessment: " + e.message, "error");
    }
  };

  // Delete a saved assessment
  const deleteSavedAssessment = async (filename) => {
    if (!confirm("Delete this saved assessment?")) return;
    try {
      const data = await api.deleteSavedAssessment(filename);
      if (data.error) {
        addToast("Error deleting: " + data.error, "error");
      } else {
        addToast("Assessment deleted", "success");
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error deleting assessment: " + e.message, "error");
    }
  };

  // Grade assessment answers with AI
  const gradeAssessmentAnswersHandler = async () => {
    if (!generatedAssessment || Object.keys(assessmentAnswers).length === 0) {
      addToast("Please answer at least one question first", "warning");
      return;
    }
    setGradingAssessment(true);
    setAssessmentGradingResults(null);
    try {
      const data = await api.gradeAssessmentAnswers(generatedAssessment, assessmentAnswers);
      if (data.error) {
        addToast("Error grading: " + data.error, "error");
      } else if (data.results) {
        setAssessmentGradingResults(data.results);
        addToast(`Graded! Score: ${data.results.score}/${data.results.total_points} (${data.results.percentage}%)`, "success");
      }
      if (data.usage) addToast("Grading cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
    } catch (e) {
      addToast("Error grading assessment: " + e.message, "error");
    } finally {
      setGradingAssessment(false);
    }
  };

  return {
    saveAssessmentHandler,
    fetchSavedLessons,
    fetchSavedAssessments,
    loadSavedAssessment,
    deleteSavedAssessment,
    gradeAssessmentAnswersHandler,
  };
}
