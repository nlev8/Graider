import React from "react";
import TeacherClassesCard from "./planner-dashboard/TeacherClassesCard";
import TagFilterBar from "./planner-dashboard/TagFilterBar";
import PublishedContentList from "./planner-dashboard/PublishedContentList";
import SharedResourcesCard from "./planner-dashboard/SharedResourcesCard";
import SubmissionsDetailPanel from "./planner-dashboard/SubmissionsDetailPanel";
import SavedAssessmentsCard from "./planner-dashboard/SavedAssessmentsCard";

/**
 * CQ wave-7 split: this shell owns the page layout (fade-in wrapper + the
 * results grid whose column count depends on selectedAssessmentResults);
 * each card/section is a stateless component in planner-dashboard/*. The
 * component is fully prop-driven (no local state or hooks), so every child
 * receives its slice of the same props the monolith destructured.
 * Conditional sections (`{cond && ...}`) became early-return-null children
 * rendered unconditionally (house pattern).
 */
export default function PlannerDashboard({ addToast, allTeacherTags, contentSubmissionsGroups, deletePublishedAssessment, deleteSavedAssessment, fetchAssessmentResults, fetchPublishedAssessments, fetchSavedAssessments, fetchSharedResources, fetchTeacherClasses, fetchTeacherTags, handleDeleteAllSharedResources, handleDeleteSharedResource, inProgressDrafts, itemMatchesTagFilter, loadSavedAssessment, loadingPublished, loadingResults, loadingSavedAssessments, loadingSharedResources, publishedAssessments, renderTagRow, savedAssessments, selectedAssessmentResults, selectedTagFilter, setAttemptDrawerStudent, setInProgressDrafts, setPublishedAssessments, setSelectedAssessmentResults, setSelectedTagFilter, setSharedResources, sharedResources, teacherClasses, toggleAssessmentStatus }) {
  return (
                    <div className="fade-in">
                      {/* Teacher's Classes */}
                      <TeacherClassesCard
                        fetchTeacherClasses={fetchTeacherClasses}
                        teacherClasses={teacherClasses}
                      />
                      {/* Global tag filter — Content Tagging */}
                      <TagFilterBar
                        allTeacherTags={allTeacherTags}
                        selectedTagFilter={selectedTagFilter}
                        setSelectedTagFilter={setSelectedTagFilter}
                      />
                      <div style={{ display: "grid", gridTemplateColumns: selectedAssessmentResults ? "1fr 1fr" : "1fr", gap: "25px" }}>
                        {/* Published Content Lists — separated by content type */}
                        <PublishedContentList
                          deletePublishedAssessment={deletePublishedAssessment}
                          fetchAssessmentResults={fetchAssessmentResults}
                          fetchPublishedAssessments={fetchPublishedAssessments}
                          fetchSharedResources={fetchSharedResources}
                          fetchTeacherTags={fetchTeacherTags}
                          itemMatchesTagFilter={itemMatchesTagFilter}
                          loadingPublished={loadingPublished}
                          publishedAssessments={publishedAssessments}
                          renderTagRow={renderTagRow}
                          selectedAssessmentResults={selectedAssessmentResults}
                          setPublishedAssessments={setPublishedAssessments}
                          toggleAssessmentStatus={toggleAssessmentStatus}
                        />

                        {/* Shared Resources Section */}
                        <SharedResourcesCard
                          handleDeleteAllSharedResources={handleDeleteAllSharedResources}
                          handleDeleteSharedResource={handleDeleteSharedResource}
                          itemMatchesTagFilter={itemMatchesTagFilter}
                          loadingSharedResources={loadingSharedResources}
                          renderTagRow={renderTagRow}
                          setSharedResources={setSharedResources}
                          sharedResources={sharedResources}
                        />

                        {/* Submissions Detail Panel */}
                        <SubmissionsDetailPanel
                          addToast={addToast}
                          contentSubmissionsGroups={contentSubmissionsGroups}
                          inProgressDrafts={inProgressDrafts}
                          loadingResults={loadingResults}
                          selectedAssessmentResults={selectedAssessmentResults}
                          setAttemptDrawerStudent={setAttemptDrawerStudent}
                          setInProgressDrafts={setInProgressDrafts}
                          setSelectedAssessmentResults={setSelectedAssessmentResults}
                        />
                      </div>

                      {/* Saved Assessments Section */}
                      <SavedAssessmentsCard
                        deleteSavedAssessment={deleteSavedAssessment}
                        fetchSavedAssessments={fetchSavedAssessments}
                        loadSavedAssessment={loadSavedAssessment}
                        loadingSavedAssessments={loadingSavedAssessments}
                        savedAssessments={savedAssessments}
                      />
                    </div>
  );
}
