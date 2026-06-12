import * as api from "../services/api";
import { domainNamesBySubject } from "./appConstants";
import { useAssessmentAuthoring } from "../hooks/useAssessmentAuthoring";
import { useSavedAssessmentActions } from "../hooks/useSavedAssessmentActions";
import { useTeacherDashboardActions } from "../hooks/useTeacherDashboardActions";
import { useResultsCurveAndEmail } from "../hooks/useResultsCurveAndEmail";

/*
 * useAppPlannerResultsHandlers — segment 7 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 1675-1940 (minus
 * domainNamesBySubject — hoisted to ./appConstants.js — and minus
 * fetchTeacherClasses, relocated to useAppAssessmentDashboardState; see that
 * hook's header): standards helpers, exportLessonPlanHandler,
 * useAssessmentAuthoring, useSavedAssessmentActions,
 * useTeacherDashboardActions, itemMatchesTagFilter, the active-assignment
 * trio (still passed to PlannerTab as props exactly as before), openReview,
 * updateGrade, and useResultsCurveAndEmail.
 * See useAppCoreState for the hook-order contract.
 */
export function useAppPlannerResultsHandlers(ctx) {
  const {
    addToast, assessmentAnswers, assessmentConfig, config, contentOnly, curveModal, editedEmails,
    editedResults, emailPreview, generatedAssessment, generatedAssignment, getDefaultEmailBody,
    globalAINotes, lessonPlan, resultsPeriodFilter, saveAssessmentName, selectedAssessmentResults,
    selectedSources, selectedStandards, selectedTagFilter, setAllTeacherTags, setAssessmentAnswers,
    setAssessmentGradingResults, setAssessmentLoading, setContentSubmissionsGroups, setCurveModal,
    setEditedEmails, setEditedResults, setEmailApprovals, setEmailPreview, setEmailStatus,
    setGeneratedAssessment, setGeneratedAssignment, setGradingAssessment, setInProgressDrafts,
    setLessonPlan, setLoadingPublished, setLoadingResults, setLoadingSavedAssessments,
    setLoadingSharedResources, setOutlookSendPolling, setOutlookSendStatus,
    setPublishedAssessments, setReviewModal, setSaveAssessmentName, setSavedAssessments,
    setSavedLessons, setSavingAssessment, setSelectedAssessmentResults, setSelectedStandards,
    setSharedResources, setStatus, standards, status, unitConfig, uploadedDocs,
  } = ctx;

  // Planner functions
  const domainNameMap = domainNamesBySubject[config.subject] || domainNamesBySubject.Math;

  const scrollToDomain = (ref, domain) => {
    const container = ref.current;
    if (!container) return;
    const target = container.querySelector('[data-domain="' + domain + '"]');
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const getDomains = (stds) => {
    const seen = [];
    stds.forEach((s) => {
      const parts = s.code.split(".");
      const domain = parts.length >= 3 ? parts[2] : "";
      if (domain && !seen.includes(domain)) seen.push(domain);
    });
    return seen;
  };

  const toggleStandard = (code) => {
    setSelectedStandards((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  // brainstormIdeasHandler + generateLessonPlan moved into PlannerTab in
  // PR 8d (lesson-gen big cluster). Both close over plannerLoading,
  // brainstormLoading, brainstormIdeas, selectedIdea, lessonVariations,
  // assignmentQuestionCounts — all of which moved with them.

  const exportLessonPlanHandler = async () => {
    if (!lessonPlan) return;
    try {
      const data = await api.exportLessonPlan(lessonPlan);
      if (data.error) addToast("Error exporting: " + data.error, "error");
      else addToast("Lesson plan exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  // Reference document upload handlers
  // handleDocUpload moved into PlannerTab in PR 8b (doc upload cluster).

  // removeUploadedDoc + handleMatchStandards moved into PlannerTab in
  // PR 8a (matching cluster). removeUploadedDoc moved with the cluster
  // because it called setMatchResults(null) on doc removal.

  // Assessment generation handlers
  // Assessment authoring handlers extracted to useAssessmentAuthoring (decomp slice 9).
  const {
    generateAssessmentHandler,
    redistributePoints,
    exportAssessmentHandler,
    exportAssessmentForPlatformHandler,
  } = useAssessmentAuthoring({
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
  });


  // publishAssessmentHandler / loadPublishModalStudents /
  // handleContentTypeChange / confirmPublishAssessment moved into
  // PlannerTab in PR 7c (publish cluster).

  // Saved-assessment / saved-lesson handlers extracted to useSavedAssessmentActions (decomp slice 17).
  const {
    saveAssessmentHandler,
    fetchSavedLessons,
    fetchSavedAssessments,
    loadSavedAssessment,
    deleteSavedAssessment,
    gradeAssessmentAnswersHandler,
  } = useSavedAssessmentActions({
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
  });

  // Fetch published assessments for teacher dashboard
  // Teacher-dashboard / publish / resource handlers extracted to useTeacherDashboardActions (decomp slice 11).
  const {
    fetchPublishedAssessments,
    fetchSharedResources,
    fetchTeacherTags,
    handleDeleteSharedResource,
    handleDeleteAllSharedResources,
    fetchContentSubmissions,
    fetchAssessmentResults,
    toggleAssessmentStatus,
    deletePublishedAssessment,
  } = useTeacherDashboardActions({
  addToast,
  selectedAssessmentResults,
  setLoadingPublished,
  setPublishedAssessments,
  setLoadingSharedResources,
  setSharedResources,
  setAllTeacherTags,
  setContentSubmissionsGroups,
  setLoadingResults,
  setSelectedAssessmentResults,
  setInProgressDrafts,
  });

  // handleSetUnit / handleSetTags / handleAddTag / handleRemoveTag moved
  // into PlannerTab in PR 7e (NewUnit + tag cluster). They were the closure
  // set behind renderTagRow; the helper moved with them.

  var itemMatchesTagFilter = function(item) {
    if (selectedTagFilter === 'all') return true;
    if (item.unit_name && item.unit_name === selectedTagFilter) return true;
    var tags = item.tags || [];
    return tags.indexOf(selectedTagFilter) !== -1;
  };

  // renderTagRow helper moved into PlannerTab in PR 7e (NewUnit + tag cluster).



  // generateAssignmentFromLessonHandler deleted in PR 8d. It had no call
  // sites anywhere in the frontend (verified via grep) — orphaned dead
  // code. Its private states (assignmentLoading, assignmentType) were
  // also dead and were removed alongside it.

  // ── Question Edit Mode Handlers ──

  /** Get the active assignment object (could be generatedAssignment, lessonPlan with sections, or generatedAssessment) */
  const getActiveAssignment = () => {
    if (generatedAssignment) return generatedAssignment;
    if (lessonPlan?.sections && !lessonPlan.days) return lessonPlan;
    if (generatedAssessment) return generatedAssessment;
    return null;
  };

  /** Set the active assignment object back into whichever state holds it */
  const setActiveAssignment = (updated) => {
    if (generatedAssignment) {
      setGeneratedAssignment(updated);
    } else if (lessonPlan?.sections && !lessonPlan.days) {
      setLessonPlan(updated);
    } else if (generatedAssessment) {
      setGeneratedAssessment(updated);
    }
  };

  /** Count total questions in the active assignment */
  const getTotalQuestionCount = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return 0;
    return a.sections.reduce((sum, s) => sum + (s.questions?.length || 0), 0);
  };

  // Question-editing helpers (toggleQuestionSelect, selectAllQuestions,
  // saveEditedQuestion, deleteSelectedQuestions, regenerateSelectedQuestions,
  // regenerateOneQuestion) moved into PlannerTab in PR 5 of the Planner
  // extraction sprint. They consume getActiveAssignment + setActiveAssignment
  // (still here, still passed as props) via closure inside PlannerTab.

  // Results/Email functions
  const openReview = (index) => setReviewModal({ show: true, index });

  const updateGrade = (index, field, value) => {
    const updated = [...editedResults];
    updated[index] = { ...updated[index], [field]: value, edited: true };
    if (field === "score") {
      const score = parseInt(value) || 0;
      updated[index].letter_grade =
        score >= 90
          ? "A"
          : score >= 80
            ? "B"
            : score >= 70
              ? "C"
              : score >= 60
                ? "D"
                : "F";
    }
    setEditedResults(updated);

    // Also sync to status.results so the table updates immediately
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      updatedResults[index] = { ...updatedResults[index], [field]: value, edited: true };
      if (field === "score") {
        const score = parseInt(value) || 0;
        updatedResults[index].letter_grade =
          score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : score >= 60 ? "D" : "F";
      }
      return { ...prev, results: updatedResults };
    });
  };

  // Helper to get letter grade from score
  // Results curve + email/approval handlers extracted to useResultsCurveAndEmail (decomp slice 12).
  const {
    applyCurve,
    sendEmails,
    sendSingleEmail,
    updateApprovalStatus,
    updateApprovalsBulk,
  } = useResultsCurveAndEmail({
  addToast,
  status,
  resultsPeriodFilter,
  editedResults,
  editedEmails,
  curveModal,
  emailPreview,
  config,
  getDefaultEmailBody,
  setEditedResults,
  setEditedEmails,
  setStatus,
  setCurveModal,
  setEmailPreview,
  setEmailStatus,
  setEmailApprovals,
  setOutlookSendPolling,
  setOutlookSendStatus,
  });

  return {
    domainNameMap, scrollToDomain, getDomains, toggleStandard, exportLessonPlanHandler,
    generateAssessmentHandler, redistributePoints, exportAssessmentHandler,
    exportAssessmentForPlatformHandler, saveAssessmentHandler, fetchSavedLessons,
    fetchSavedAssessments, loadSavedAssessment, deleteSavedAssessment,
    gradeAssessmentAnswersHandler, fetchPublishedAssessments, fetchSharedResources,
    fetchTeacherTags, handleDeleteSharedResource, handleDeleteAllSharedResources,
    fetchContentSubmissions, fetchAssessmentResults, toggleAssessmentStatus,
    deletePublishedAssessment, itemMatchesTagFilter, getActiveAssignment, setActiveAssignment,
    getTotalQuestionCount, openReview, updateGrade, applyCurve, sendEmails, sendSingleEmail,
    updateApprovalStatus, updateApprovalsBulk,
  };
}
