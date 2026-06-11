import React from "react";
import PlannerLesson from "../../components/PlannerLesson";

/*
 * PlannerLessonMode — the lesson-mode mount of PlannerLesson, relocated
 * verbatim from PlannerTab.jsx (CQ wave-3 split). The pre-split
 * `{plannerMode === "lesson" && (...)}` guard becomes the early return
 * (house pattern). PlannerLesson itself is untouched and receives the
 * byte-identical explicit prop list.
 */
export default function PlannerLessonMode(props) {
  const {
    plannerMode,
    addToast, assignment, assignmentQuestionCounts, assignmentSectionsOpen,
    brainstormIdeas, brainstormIdeasHandler, brainstormLoading, config,
    contentOnly, deleteSelectedQuestions, docUploading, domainNameMap,
    editMode, editingQuestion, expandedStandards, exportLessonPlanHandler,
    generateLessonPlan, generatedAssignment, getDomains, getTotalQuestionCount,
    handleDocUpload, handleMatchStandards, lessonPlan, lessonVariations,
    matchResults, matchingInProgress, plannerLoading, previewResults,
    previewShowAnswers, publishAssessmentHandler, publishingAssessment,
    regenerateOneQuestion, regenerateSelectedQuestions, regeneratingQuestions,
    removeUploadedDoc, saveEditedQuestion, scrollToDomain, selectAllQuestions,
    selectedIdea, selectedQuestions, selectedStandards, setActiveTab,
    setAssignment, setAssignmentQuestionCounts, setAssignmentSectionsOpen,
    setBrainstormIdeas, setContentOnly, setEditMode, setEditingQuestion,
    setExpandedStandards, setGeneratedAssignment, setLessonPlan,
    setLessonVariations, setLoadedAssignmentName, setPlannerMode,
    setPreviewResults, setPreviewShowAnswers, setSelectedIdea,
    setSelectedQuestions, setSelectedStandards, setShowSaveLesson,
    setUnitConfig, standards, standardsScrollRef, toggleQuestionSelect,
    toggleStandard, unitConfig, uploadedDocs, user,
  } = props;

  if (!(plannerMode === "lesson")) return null;

  return (
                    <PlannerLesson
                      addToast={addToast}
                      assignment={assignment}
                      assignmentQuestionCounts={assignmentQuestionCounts}
                      assignmentSectionsOpen={assignmentSectionsOpen}
                      brainstormIdeas={brainstormIdeas}
                      brainstormIdeasHandler={brainstormIdeasHandler}
                      brainstormLoading={brainstormLoading}
                      config={config}
                      contentOnly={contentOnly}
                      deleteSelectedQuestions={deleteSelectedQuestions}
                      docUploading={docUploading}
                      domainNameMap={domainNameMap}
                      editMode={editMode}
                      editingQuestion={editingQuestion}
                      expandedStandards={expandedStandards}
                      exportLessonPlanHandler={exportLessonPlanHandler}
                      generateLessonPlan={generateLessonPlan}
                      generatedAssignment={generatedAssignment}
                      getDomains={getDomains}
                      getTotalQuestionCount={getTotalQuestionCount}
                      handleDocUpload={handleDocUpload}
                      handleMatchStandards={handleMatchStandards}
                      lessonPlan={lessonPlan}
                      lessonVariations={lessonVariations}
                      matchResults={matchResults}
                      matchingInProgress={matchingInProgress}
                      plannerLoading={plannerLoading}
                      previewResults={previewResults}
                      previewShowAnswers={previewShowAnswers}
                      publishAssessmentHandler={publishAssessmentHandler}
                      publishingAssessment={publishingAssessment}
                      regenerateOneQuestion={regenerateOneQuestion}
                      regenerateSelectedQuestions={regenerateSelectedQuestions}
                      regeneratingQuestions={regeneratingQuestions}
                      removeUploadedDoc={removeUploadedDoc}
                      saveEditedQuestion={saveEditedQuestion}
                      scrollToDomain={scrollToDomain}
                      selectAllQuestions={selectAllQuestions}
                      selectedIdea={selectedIdea}
                      selectedQuestions={selectedQuestions}
                      selectedStandards={selectedStandards}
                      setActiveTab={setActiveTab}
                      setAssignment={setAssignment}
                      setAssignmentQuestionCounts={setAssignmentQuestionCounts}
                      setAssignmentSectionsOpen={setAssignmentSectionsOpen}
                      setBrainstormIdeas={setBrainstormIdeas}
                      setContentOnly={setContentOnly}
                      setEditMode={setEditMode}
                      setEditingQuestion={setEditingQuestion}
                      setExpandedStandards={setExpandedStandards}
                      setGeneratedAssignment={setGeneratedAssignment}
                      setLessonPlan={setLessonPlan}
                      setLessonVariations={setLessonVariations}
                      setLoadedAssignmentName={setLoadedAssignmentName}
                      setPlannerMode={setPlannerMode}
                      setPreviewResults={setPreviewResults}
                      setPreviewShowAnswers={setPreviewShowAnswers}
                      setSelectedIdea={setSelectedIdea}
                      setSelectedQuestions={setSelectedQuestions}
                      setSelectedStandards={setSelectedStandards}
                      setShowSaveLesson={setShowSaveLesson}
                      setUnitConfig={setUnitConfig}
                      standards={standards}
                      standardsScrollRef={standardsScrollRef}
                      toggleQuestionSelect={toggleQuestionSelect}
                      toggleStandard={toggleStandard}
                      unitConfig={unitConfig}
                      uploadedDocs={uploadedDocs}
                      user={user}
                    />
  );
}
