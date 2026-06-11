import React from "react";
import PlannerDashboard from "../../components/PlannerDashboard";

/*
 * PlannerDashboardMode — the dashboard-mode mount of PlannerDashboard,
 * relocated verbatim from PlannerTab.jsx (CQ wave-3 split). The pre-split
 * `{plannerMode === "dashboard" && (...)}` guard becomes the early return
 * (house pattern). PlannerDashboard itself is untouched and receives the
 * byte-identical explicit prop list.
 */
export default function PlannerDashboardMode(props) {
  const {
    plannerMode,
    addToast, allTeacherTags, contentSubmissionsGroups,
    deletePublishedAssessment, deleteSavedAssessment, fetchAssessmentResults,
    fetchPublishedAssessments, fetchSavedAssessments, fetchSharedResources,
    fetchTeacherClasses, fetchTeacherTags, handleDeleteAllSharedResources,
    handleDeleteSharedResource, inProgressDrafts, itemMatchesTagFilter,
    loadSavedAssessment, loadingPublished, loadingResults,
    loadingSavedAssessments, loadingSharedResources, publishedAssessments,
    renderTagRow, savedAssessments, selectedAssessmentResults,
    selectedTagFilter, setAttemptDrawerStudent, setInProgressDrafts,
    setPublishedAssessments, setSelectedAssessmentResults,
    setSelectedTagFilter, setSharedResources, sharedResources,
    teacherClasses, toggleAssessmentStatus,
  } = props;

  if (!(plannerMode === "dashboard")) return null;

  return (
                    <PlannerDashboard
                      addToast={addToast}
                      allTeacherTags={allTeacherTags}
                      contentSubmissionsGroups={contentSubmissionsGroups}
                      deletePublishedAssessment={deletePublishedAssessment}
                      deleteSavedAssessment={deleteSavedAssessment}
                      fetchAssessmentResults={fetchAssessmentResults}
                      fetchPublishedAssessments={fetchPublishedAssessments}
                      fetchSavedAssessments={fetchSavedAssessments}
                      fetchSharedResources={fetchSharedResources}
                      fetchTeacherClasses={fetchTeacherClasses}
                      fetchTeacherTags={fetchTeacherTags}
                      handleDeleteAllSharedResources={handleDeleteAllSharedResources}
                      handleDeleteSharedResource={handleDeleteSharedResource}
                      inProgressDrafts={inProgressDrafts}
                      itemMatchesTagFilter={itemMatchesTagFilter}
                      loadSavedAssessment={loadSavedAssessment}
                      loadingPublished={loadingPublished}
                      loadingResults={loadingResults}
                      loadingSavedAssessments={loadingSavedAssessments}
                      loadingSharedResources={loadingSharedResources}
                      publishedAssessments={publishedAssessments}
                      renderTagRow={renderTagRow}
                      savedAssessments={savedAssessments}
                      selectedAssessmentResults={selectedAssessmentResults}
                      selectedTagFilter={selectedTagFilter}
                      setAttemptDrawerStudent={setAttemptDrawerStudent}
                      setInProgressDrafts={setInProgressDrafts}
                      setPublishedAssessments={setPublishedAssessments}
                      setSelectedAssessmentResults={setSelectedAssessmentResults}
                      setSelectedTagFilter={setSelectedTagFilter}
                      setSharedResources={setSharedResources}
                      sharedResources={sharedResources}
                      teacherClasses={teacherClasses}
                      toggleAssessmentStatus={toggleAssessmentStatus}
                    />
  );
}
