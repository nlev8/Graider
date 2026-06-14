import React from "react";
import PlannerCalendar from "../../components/PlannerCalendar";
import PlannerTools from "../../components/PlannerTools";
import PlannerModeToggle from "./PlannerModeToggle";
import PlannerLessonMode from "./PlannerLessonMode";
import PlannerAssessmentMode from "./PlannerAssessmentMode";
import PlannerDashboardMode from "./PlannerDashboardMode";
import PlannerModals from "./PlannerModals";

/*
 * PlannerTabBody — pure-prop JSX subtree extracted from PlannerTab (cq8-07).
 *
 * Receives the full rendered content of PlannerTab as props; owns no state,
 * no effects, no fetch logic. All state/hooks stay in PlannerTab.
 *
 * Prop groups:
 *   - passthroughProps  : original {...props} spread from PlannerTab
 *   - lessonGen         : useLessonGeneration hook object
 *   - docs              : usePlannerDocs hook object
 *   - questionEditing   : useQuestionEditing hook object
 *   - publish           : usePublishAssessment hook object
 *   - share             : useShareWithClasses hook object
 *   - tagRow            : useTagRow hook object
 *   - local*            : PlannerTab-owned state/derived values threaded as named props
 */
export default function PlannerTabBody({
  // pass-through: the original props object received by PlannerTab
  passthroughProps,
  // hook objects
  lessonGen,
  docs,
  questionEditing,
  publish,
  share,
  tagRow,
  // local states from PlannerTab
  expandedStandards,
  setExpandedStandards,
  assignmentSectionsOpen,
  setAssignmentSectionsOpen,
  previewShowAnswers,
  setPreviewShowAnswers,
  sectionsDropdownOpen,
  setSectionsDropdownOpen,
  showPlatformExport,
  setShowPlatformExport,
  attemptDrawerStudent,
  setAttemptDrawerStudent,
  showSaveLesson,
  setShowSaveLesson,
  saveLessonUnit,
  setSaveLessonUnit,
  newUnitName,
  setNewUnitName,
  savedUnits,
}) {
  // Frequently-referenced props destructured for prop threading below.
  const {
    plannerMode, setPlannerMode,
    fetchPublishedAssessments, fetchSharedResources, fetchTeacherTags,
    fetchSavedAssessments, fetchSavedLessons,
    activeTab, addToast,
    savedLessons, supportDocs, setSupportDocs,
    config, lessonPlan, generatedAssignment, globalAINotes, uploadedDocs,
    teacherClasses, periods, studentAccommodations,
    setSharedResources, setPublishedAssessments,
  } = passthroughProps;

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
          {...passthroughProps}. */}
      <PlannerLessonMode
        {...passthroughProps}
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
        {...passthroughProps}
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
        {...passthroughProps}
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
