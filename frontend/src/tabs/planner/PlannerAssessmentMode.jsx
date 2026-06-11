import React from "react";
import PlannerAssessment from "../../components/PlannerAssessment";

/*
 * PlannerAssessmentMode — the assessment-mode mount of PlannerAssessment,
 * relocated verbatim from PlannerTab.jsx (CQ wave-3 split). The pre-split
 * `{plannerMode === "assessment" && (...)}` guard becomes the early return
 * (house pattern). PlannerAssessment itself is untouched and receives the
 * byte-identical explicit prop list.
 */
export default function PlannerAssessmentMode(props) {
  const {
    plannerMode,
    assessmentAnswers, assessmentConfig, assessmentLoading,
    assessmentStandardsScrollRef, deleteSelectedQuestions, distributeDOK,
    distributePoints, distributeQuestions, domainNameMap, editMode,
    editingQuestion, exportAssessmentForPlatformHandler,
    exportAssessmentHandler, fetchSavedLessons, generateAssessmentHandler,
    generatedAssessment, getDomains, getTotalQuestionCount,
    gradeAssessmentAnswersHandler, gradingAssessment, periods, plannerLoading,
    previewShowAnswers, publishAssessmentHandler, publishingAssessment,
    redistributePoints, regenerateOneQuestion, regenerateSelectedQuestions,
    regeneratingQuestions, saveAssessmentHandler, saveAssessmentName,
    saveEditedQuestion, savedAssignmentData, savedAssignments, savedLessons,
    savingAssessment, scrollToDomain, sectionsDropdownOpen, selectAllQuestions,
    selectedQuestions, selectedSources, selectedStandards,
    setAssessmentAnswers, setAssessmentConfig, setEditMode,
    setEditingQuestion, setGeneratedAssessment, setSaveAssessmentName,
    setSectionsDropdownOpen, setSelectedQuestions, setSelectedSources,
    setSelectedStandards, setShowPlatformExport, showPlatformExport,
    standards, toggleQuestionSelect, toggleStandard, uploadedDocs,
  } = props;

  if (!(plannerMode === "assessment")) return null;

  return (
                    <PlannerAssessment
                      assessmentAnswers={assessmentAnswers}
                      assessmentConfig={assessmentConfig}
                      assessmentLoading={assessmentLoading}
                      assessmentStandardsScrollRef={assessmentStandardsScrollRef}
                      deleteSelectedQuestions={deleteSelectedQuestions}
                      distributeDOK={distributeDOK}
                      distributePoints={distributePoints}
                      distributeQuestions={distributeQuestions}
                      domainNameMap={domainNameMap}
                      editMode={editMode}
                      editingQuestion={editingQuestion}
                      exportAssessmentForPlatformHandler={exportAssessmentForPlatformHandler}
                      exportAssessmentHandler={exportAssessmentHandler}
                      fetchSavedLessons={fetchSavedLessons}
                      generateAssessmentHandler={generateAssessmentHandler}
                      generatedAssessment={generatedAssessment}
                      getDomains={getDomains}
                      getTotalQuestionCount={getTotalQuestionCount}
                      gradeAssessmentAnswersHandler={gradeAssessmentAnswersHandler}
                      gradingAssessment={gradingAssessment}
                      periods={periods}
                      plannerLoading={plannerLoading}
                      previewShowAnswers={previewShowAnswers}
                      publishAssessmentHandler={publishAssessmentHandler}
                      publishingAssessment={publishingAssessment}
                      redistributePoints={redistributePoints}
                      regenerateOneQuestion={regenerateOneQuestion}
                      regenerateSelectedQuestions={regenerateSelectedQuestions}
                      regeneratingQuestions={regeneratingQuestions}
                      saveAssessmentHandler={saveAssessmentHandler}
                      saveAssessmentName={saveAssessmentName}
                      saveEditedQuestion={saveEditedQuestion}
                      savedAssignmentData={savedAssignmentData}
                      savedAssignments={savedAssignments}
                      savedLessons={savedLessons}
                      savingAssessment={savingAssessment}
                      scrollToDomain={scrollToDomain}
                      sectionsDropdownOpen={sectionsDropdownOpen}
                      selectAllQuestions={selectAllQuestions}
                      selectedQuestions={selectedQuestions}
                      selectedSources={selectedSources}
                      selectedStandards={selectedStandards}
                      setAssessmentAnswers={setAssessmentAnswers}
                      setAssessmentConfig={setAssessmentConfig}
                      setEditMode={setEditMode}
                      setEditingQuestion={setEditingQuestion}
                      setGeneratedAssessment={setGeneratedAssessment}
                      setSaveAssessmentName={setSaveAssessmentName}
                      setSectionsDropdownOpen={setSectionsDropdownOpen}
                      setSelectedQuestions={setSelectedQuestions}
                      setSelectedSources={setSelectedSources}
                      setSelectedStandards={setSelectedStandards}
                      setShowPlatformExport={setShowPlatformExport}
                      showPlatformExport={showPlatformExport}
                      standards={standards}
                      toggleQuestionSelect={toggleQuestionSelect}
                      toggleStandard={toggleStandard}
                      uploadedDocs={uploadedDocs}
                    />
  );
}
