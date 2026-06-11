import React from "react";
import PublishedAssessmentModal from "../../components/PublishedAssessmentModal";
import PublishContentModal from "../../components/PublishContentModal";
import ShareWithClassesModal from "../../components/ShareWithClassesModal";
import AttemptDrawer from "../../components/AttemptDrawer";
import PlannerNewUnitModal from "./PlannerNewUnitModal";
import SaveLessonModal from "./SaveLessonModal";

/*
 * PlannerModals — the always-rendered drawer/modal mounts at the bottom of
 * the planner tree, relocated verbatim from PlannerTab.jsx (CQ wave-3
 * split). Each modal guards its own visibility via its `open`/`student`
 * prop exactly as before; state ownership is unchanged (publish cluster in
 * usePublishAssessment, share cluster in useShareWithClasses, newUnitModal
 * in useTagRow, save-lesson slice in the PlannerTab shell).
 */
export default function PlannerModals(props) {
  const {
    // AttemptDrawer (PR 7a)
    attemptDrawerStudent, setAttemptDrawerStudent,
    // Publish cluster (PR 7c) — spread from usePublishAssessment
    showPublishModal, setShowPublishModal, publishSettings, setPublishSettings,
    publishClassId, setPublishClassId, loadPublishModalStudents,
    publishModalStudents, loadingPublishStudents, publishingAssessment,
    confirmPublishAssessment, publishedAssessmentModal, setPublishedAssessmentModal,
    // ShareWithClasses cluster (PR 7d) — spread from useShareWithClasses
    showShareModal, setShowShareModal, shareModalContent, setShareModalContent,
    shareModalSelected, setShareModalSelected, shareModalSharing,
    executeShareWithClasses,
    // NewUnit + tag cluster (PR 7e)
    newUnitModal, setNewUnitModal,
    // Save Lesson modal slice (PR 6b)
    showSaveLesson, setShowSaveLesson, lessonPlan, saveLessonUnit,
    setSaveLessonUnit, newUnitName, setNewUnitName, savedUnits,
    fetchSavedLessons,
    // App-shell props
    teacherClasses, periods, studentAccommodations, addToast,
    setSharedResources, setPublishedAssessments, fetchTeacherTags,
  } = props;

  return (
    <>
      {/* AttemptDrawer — moved from App.jsx in PR 7a. */}
      <AttemptDrawer
        student={attemptDrawerStudent}
        onClose={() => setAttemptDrawerStudent(null)}
      />

      {/* PublishContentModal — moved from App.jsx in PR 7c. */}
      <PublishContentModal
        open={showPublishModal}
        onClose={() => setShowPublishModal(false)}
        settings={publishSettings}
        setSettings={setPublishSettings}
        classId={publishClassId}
        setClassId={setPublishClassId}
        teacherClasses={teacherClasses}
        periods={periods}
        onPeriodChange={loadPublishModalStudents}
        modalStudents={publishModalStudents}
        loadingStudents={loadingPublishStudents}
        studentAccommodations={studentAccommodations}
        publishing={publishingAssessment}
        onPublish={confirmPublishAssessment}
      />

      {/* PublishedAssessmentModal — moved from App.jsx in PR 7c. */}
      <PublishedAssessmentModal
        open={publishedAssessmentModal.show}
        onClose={() => setPublishedAssessmentModal({ show: false, joinCode: "", joinLink: "" })}
        joinCode={publishedAssessmentModal.joinCode}
        joinLink={publishedAssessmentModal.joinLink}
        isClassBased={publishedAssessmentModal.isClassBased}
        onCopied={() => addToast("Link copied to clipboard!", "success")}
      />

      {/* ShareWithClassesModal — moved from App.jsx in PR 7d. */}
      <ShareWithClassesModal
        open={showShareModal}
        onClose={() => setShowShareModal(false)}
        content={shareModalContent}
        setContent={setShareModalContent}
        selectedIds={shareModalSelected}
        setSelectedIds={setShareModalSelected}
        sharing={shareModalSharing}
        classes={teacherClasses}
        onShare={executeShareWithClasses}
      />

      {/* New Unit Name Modal — moved from App.jsx in PR 7e (NewUnit + tag cluster). */}
      <PlannerNewUnitModal
        newUnitModal={newUnitModal}
        setNewUnitModal={setNewUnitModal}
        setSharedResources={setSharedResources}
        setPublishedAssessments={setPublishedAssessments}
        addToast={addToast}
        fetchTeacherTags={fetchTeacherTags}
      />

      {/* Save Lesson Modal — moved from App.jsx:7853-7956 in PR 6b. */}
      <SaveLessonModal
        showSaveLesson={showSaveLesson}
        setShowSaveLesson={setShowSaveLesson}
        lessonPlan={lessonPlan}
        saveLessonUnit={saveLessonUnit}
        setSaveLessonUnit={setSaveLessonUnit}
        newUnitName={newUnitName}
        setNewUnitName={setNewUnitName}
        savedUnits={savedUnits}
        addToast={addToast}
        fetchSavedLessons={fetchSavedLessons}
      />
    </>
  );
}
