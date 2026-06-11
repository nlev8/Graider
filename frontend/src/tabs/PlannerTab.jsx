import React, { useState, useEffect } from "react";
import PlannerCalendar from "../components/PlannerCalendar";
import PlannerTools from "../components/PlannerTools";
import { useQuestionEditing } from "../hooks/useQuestionEditing";
import PlannerModeToggle from "./planner/PlannerModeToggle";
import PlannerLessonMode from "./planner/PlannerLessonMode";
import PlannerAssessmentMode from "./planner/PlannerAssessmentMode";
import PlannerDashboardMode from "./planner/PlannerDashboardMode";
import PlannerModals from "./planner/PlannerModals";
import usePublishAssessment from "./planner/usePublishAssessment";
import useShareWithClasses from "./planner/useShareWithClasses";
import useTagRow from "./planner/useTagRow";
import useLessonGeneration from "./planner/useLessonGeneration";
import usePlannerDocs from "./planner/usePlannerDocs";

/*
 * Planner tab — thin orchestrator (CQ wave-3 split).
 *
 * Originally a pure JSX lift from App.jsx:7574-13515 (PR 1 of the Planner
 * extraction sprint, docs/superpowers/plans/2026-05-04-planner-tab-extraction.md);
 * PRs 2-8d progressively moved ~91 Planner-only state pairs into this
 * component. This revision splits the resulting 1,425-line component function
 * into ./planner/* (wave-1/2 tabs/analytics + tabs/grade precedent) —
 * behavior-preserving, no logic changes:
 *   - usePublishAssessment / useShareWithClasses / useTagRow /
 *     useLessonGeneration / usePlannerDocs hooks (state clusters from
 *     PRs 6a-8d, relocated verbatim; effect dep arrays byte-identical)
 *   - PlannerModeToggle + PlannerLessonMode / PlannerAssessmentMode /
 *     PlannerDashboardMode mounts + PlannerNewUnitModal + SaveLessonModal
 *
 * State ownership is unchanged: truly-shared state stays in App.jsx and
 * arrives as props; Planner-owned clusters live in the hooks above; the
 * cross-cluster glue states below stay in this shell.
 */

export default function PlannerTab(props) {
  const {

    // App-shell state (read-only) — confirmed shared per plan #190
    status, setStatus, config, setConfig, user, activeTab, addToast,
    // 21 truly-shared states from plan #190
    lessonPlan, setLessonPlan,
    generatedAssignment, setGeneratedAssignment,
    assessmentConfig, setAssessmentConfig,
    selectedStandards, setSelectedStandards,
    unitConfig, setUnitConfig,
    standards, setStandards,
    assignment, setAssignment,
    uploadedDocs, setUploadedDocs,
    generatedAssessment, setGeneratedAssessment,
    rubric, setRubric,
    globalAINotes, setGlobalAINotes,
    supportDocs, setSupportDocs,
    savedAssignments, setSavedAssignments,
    teacherClasses, setTeacherClasses,
    periods, setPeriods,
    savedAssignmentData, setSavedAssignmentData,
    contentOnly, setContentOnly,
    assessmentTemplates, setAssessmentTemplates,
    uploadingTemplate, setUploadingTemplate,
    // Planner-only states that remain App-level. plannerMode stays in App
    // because TutorialOverlay (rendered at App level) drives tutorial steps
    // that flip Planner sub-modes via setPlannerMode.
    plannerMode, setPlannerMode,
    assessmentLoading, setAssessmentLoading,
    gradingAssessment, setGradingAssessment,
    savingAssessment, setSavingAssessment,
    saveAssessmentName, setSaveAssessmentName,
    assessmentAnswers, setAssessmentAnswers,
    assessmentGradingResults, setAssessmentGradingResults,
    selectedSources, setSelectedSources,
    selectedAssessmentResults, setSelectedAssessmentResults,
    publishedAssessments, setPublishedAssessments,
    loadingPublished, setLoadingPublished,
    inProgressDrafts, setInProgressDrafts,
    loadingResults, setLoadingResults,
    sharedResources, setSharedResources,
    loadingSharedResources, setLoadingSharedResources,
    contentSubmissionsGroups, setContentSubmissionsGroups,
    savedAssessments, setSavedAssessments,
    loadingSavedAssessments, setLoadingSavedAssessments,
    savedLessons, setSavedLessons,
    allTeacherTags, setAllTeacherTags,
    selectedTagFilter, setSelectedTagFilter,
    // Handlers and constants — added by build-fail iteration. Initial:
    loadAssignment, saveAssignmentConfig,

    // PR 1 Codex Round 1 additions (missing closures):
    getActiveAssignment, setActiveAssignment,
    studentAccommodations,
    domainNameMap, getDomains, scrollToDomain, toggleStandard, standardsScrollRef, assessmentStandardsScrollRef, deleteSavedAssessment, loadSavedAssessment, saveAssessmentHandler, generateAssessmentHandler, gradeAssessmentAnswersHandler, exportAssessmentHandler, exportAssessmentForPlatformHandler, deletePublishedAssessment, toggleAssessmentStatus, fetchAssessmentResults, fetchPublishedAssessments, fetchSavedAssessments, fetchSavedLessons, fetchSharedResources, fetchTeacherClasses, fetchTeacherTags, handleDeleteAllSharedResources, handleDeleteSharedResource, getTotalQuestionCount, distributeDOK, distributePoints, distributeQuestions, redistributePoints, exportLessonPlanHandler, getSubjectSectionDefaults, itemMatchesTagFilter, setActiveTab, setLoadedAssignmentName,

  } = props;

  // Save Lesson modal slice (PR 6b). `savedUnits` is derived inline from
  // `savedLessons.units` (a truly-shared App-shell prop).
  const [showSaveLesson, setShowSaveLesson] = useState(false);
  const [saveLessonUnit, setSaveLessonUnit] = useState('');
  const [newUnitName, setNewUnitName] = useState('');
  const savedUnits = Object.keys((savedLessons && savedLessons.units) || {});

  // AttemptDrawer slice (PR 7a).
  const [attemptDrawerStudent, setAttemptDrawerStudent] = useState(null);

  // showPlatformExport (PR 7b) — zero App-level usage.
  const [showPlatformExport, setShowPlatformExport] = useState(false);

  // Publish cluster (PR 7c) — ./planner/usePublishAssessment.
  const publish = usePublishAssessment({
    getActiveAssignment, generatedAssignment, lessonPlan, config, addToast,
    studentAccommodations, teacherClasses, fetchTeacherClasses,
    fetchPublishedAssessments, fetchSharedResources, fetchTeacherTags,
  });

  // ShareWithClasses cluster (PR 7d) — ./planner/useShareWithClasses.
  const share = useShareWithClasses({
    teacherClasses, setTeacherClasses, addToast, unitConfig,
  });

  // NewUnit + tag cluster (PR 7e) — ./planner/useTagRow.
  const tagRow = useTagRow({ allTeacherTags, addToast, fetchTeacherTags });

  // Lesson-core display states (PR 6a).
  const [expandedStandards, setExpandedStandards] = useState([]);
  const [assignmentSectionsOpen, setAssignmentSectionsOpen] = useState(false);
  const [previewShowAnswers, setPreviewShowAnswers] = useState(true);

  /*
   * Question-editing slice (PR 5) — owned locally by PlannerTab. The reset
   * useEffect combines the two former App-level reset effects (App.jsx:
   * 1212-1218 and 1544-1549) into one with a 3-element dep array —
   * semantically equivalent because the body is idempotent and only acts
   * when the underlying assignment ref changes.
   */
  const questionEditing = useQuestionEditing({
    getActiveAssignment, setActiveAssignment, addToast, config, unitConfig,
  });
  const [sectionsDropdownOpen, setSectionsDropdownOpen] = useState(false);

  useEffect(() => {
    questionEditing.setEditMode(false);
    questionEditing.setSelectedQuestions(new Set());
    questionEditing.setEditingQuestion(null);
    questionEditing.setRegeneratingQuestions(new Set());
  }, [lessonPlan, generatedAssignment, generatedAssessment]);

  // Matching (PR 8a) + preview (PR 8c) + doc-upload (PR 8b) clusters —
  // ./planner/usePlannerDocs.
  const docs = usePlannerDocs({
    uploadedDocs, setUploadedDocs, config, addToast, selectedStandards,
    lessonPlan, generatedAssignment,
  });

  // Lesson-gen big cluster (PR 8d) — ./planner/useLessonGeneration.
  const lessonGen = useLessonGeneration({
    activeTab, config, addToast, selectedStandards, uploadedDocs,
    standards, setStandards, unitConfig, contentOnly, setLessonPlan,
    getSubjectSectionDefaults,
  });

  // Dashboard mode triggers a teacher-classes fetch — moved from App.jsx PR 3.
  useEffect(() => {
    if (plannerMode === "dashboard") {
      fetchTeacherClasses();
    }
  }, [plannerMode]);

  return (
                <div data-tutorial="planner-card" className="fade-in">
                  {/* Mode Toggle */}
                  <PlannerModeToggle
                    plannerMode={plannerMode}
                    setPlannerMode={setPlannerMode}
                    fetchPublishedAssessments={fetchPublishedAssessments}
                    fetchSharedResources={fetchSharedResources}
                    fetchTeacherTags={fetchTeacherTags}
                    fetchSavedAssessments={fetchSavedAssessments}
                  />

                  {/* Lesson Planning Mode. Spread order is load-bearing:
                      hook-owned values override same-named leftovers in
                      {...props}. */}
                  <PlannerLessonMode
                    {...props}
                    {...lessonGen}
                    {...docs}
                    {...questionEditing}
                    expandedStandards={expandedStandards}
                    setExpandedStandards={setExpandedStandards}
                    assignmentSectionsOpen={assignmentSectionsOpen}
                    setAssignmentSectionsOpen={setAssignmentSectionsOpen}
                    previewShowAnswers={previewShowAnswers}
                    setPreviewShowAnswers={setPreviewShowAnswers}
                    publishAssessmentHandler={publish.publishAssessmentHandler}
                    publishingAssessment={publish.publishingAssessment}
                    setShowSaveLesson={setShowSaveLesson}
                  />

                  {/* Assessment Generator Mode */}
                  <PlannerAssessmentMode
                    {...props}
                    {...questionEditing}
                    plannerLoading={lessonGen.plannerLoading}
                    previewShowAnswers={previewShowAnswers}
                    publishAssessmentHandler={publish.publishAssessmentHandler}
                    publishingAssessment={publish.publishingAssessment}
                    sectionsDropdownOpen={sectionsDropdownOpen}
                    setSectionsDropdownOpen={setSectionsDropdownOpen}
                    showPlatformExport={showPlatformExport}
                    setShowPlatformExport={setShowPlatformExport}
                  />

                  {/* Student Portal Dashboard */}
                  <PlannerDashboardMode
                    {...props}
                    renderTagRow={tagRow.renderTagRow}
                    setAttemptDrawerStudent={setAttemptDrawerStudent}
                  />

                  {/* Calendar Mode */}
                  {plannerMode === "calendar" && (
                    <PlannerCalendar
                      active={activeTab === "planner"}
                      addToast={addToast}
                      savedLessons={savedLessons}
                      supportDocs={supportDocs}
                      setSupportDocs={setSupportDocs}
                    />
                  )}

                  {/* Tools Mode */}
                  {plannerMode === "tools" && (
                    <PlannerTools
                      config={config}
                      lessonPlan={lessonPlan}
                      generatedAssignment={generatedAssignment}
                      globalAINotes={globalAINotes}
                      uploadedDocs={uploadedDocs}
                      addToast={addToast}
                      shareWithClass={share.shareWithClass}
                    />
                  )}

      {/* Drawer + modal mounts (PRs 6b/7a/7c/7d/7e) — ./planner/PlannerModals. */}
      <PlannerModals
        {...publish}
        {...share}
        newUnitModal={tagRow.newUnitModal}
        setNewUnitModal={tagRow.setNewUnitModal}
        attemptDrawerStudent={attemptDrawerStudent}
        setAttemptDrawerStudent={setAttemptDrawerStudent}
        showSaveLesson={showSaveLesson}
        setShowSaveLesson={setShowSaveLesson}
        lessonPlan={lessonPlan}
        saveLessonUnit={saveLessonUnit}
        setSaveLessonUnit={setSaveLessonUnit}
        newUnitName={newUnitName}
        setNewUnitName={setNewUnitName}
        savedUnits={savedUnits}
        fetchSavedLessons={fetchSavedLessons}
        teacherClasses={teacherClasses}
        periods={periods}
        studentAccommodations={studentAccommodations}
        addToast={addToast}
        setSharedResources={setSharedResources}
        setPublishedAssessments={setPublishedAssessments}
        fetchTeacherTags={fetchTeacherTags}
      />

                </div>
  );
}
