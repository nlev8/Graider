import React, { useState } from "react";
import Icon from "../components/Icon";
import createSavedAssignmentHandlers from "./builder/createSavedAssignmentHandlers";
import SavedAssignmentsCard from "./builder/SavedAssignmentsCard";
import AssignmentDetailsSection from "./builder/AssignmentDetailsSection";
import DueDatePolicySection from "./builder/DueDatePolicySection";
import ImportDocumentSection from "./builder/ImportDocumentSection";
import MarkerLibrarySection from "./builder/MarkerLibrarySection";
import RubricTypeSection from "./builder/RubricTypeSection";
import ModelAnswersSection from "./builder/ModelAnswersSection";
import StandardsAlignmentSection from "./builder/StandardsAlignmentSection";
import QuestionsSection from "./builder/QuestionsSection";
import ExportButtonsSection from "./builder/ExportButtonsSection";

/**
 * BuilderTab - Extracted from App.jsx
 *
 * CQ wave-9 split: the 1,814-line render function now lives in
 * tabs/builder/* as stateless guarded sections; this shell keeps all
 * state (savedAssignmentsExpanded) and creates the saved-assignment
 * handlers via the createSavedAssignmentHandlers factory (same pattern
 * as the wave-5/6 splits). Props are unchanged from the pre-split
 * component — see the list below.
 *
 * Props needed:
 *
 * State variables:
 *   - assignment, setAssignment
 *   - savedAssignments, setSavedAssignments (setSavedAssignments not directly used but kept for consistency)
 *   - savedAssignmentData, setSavedAssignmentData
 *   (savedAssignmentsExpanded is now BuilderTab-owned local state, pushed down from App.jsx)
 *   - loadedAssignmentName, setLoadedAssignmentName
 *   - isLoadingAssignment, setIsLoadingAssignment
 *   - importedDoc, setImportedDoc
 *   - docEditorModal, setDocEditorModal
 *   - modelAnswersLoading
 *   - config (global settings object, needs config.subject)
 *
 * Refs:
 *   - fileInputRef
 *   - skipAutoSaveRef
 *
 * Callbacks:
 *   - loadAssignment(name)
 *   - deleteAssignment(name)
 *   - saveAssignmentConfig()
 *   - exportAssignment(format)
 *   - handleDocImport(e)
 *   - openDocEditor()
 *   - handleGenerateModelAnswers()
 *   - removeMarker(marker, index)
 *   - addQuestion()
 *   - updateQuestion(index, field, value)
 *   - removeQuestion(index)
 *   - addToast(message, type)
 *
 * Utility functions:
 *   - getMarkerText(marker)
 *   - getMarkerPoints(marker)
 *   - getMarkerType(marker)
 *   - calculateTotalPoints(markers, effortPoints)
 *   - removeAllHighlightsFromHtml(html)
 *   - applyAllHighlights(html, markers, excludeMarkers)
 *
 * Constants:
 *   - markerLibrary
 */

export default React.memo(function BuilderTab({
  assignment,
  setAssignment,
  savedAssignments,
  savedAssignmentData,
  setSavedAssignmentData,
  loadedAssignmentName,
  setLoadedAssignmentName,
  isLoadingAssignment,
  setIsLoadingAssignment,
  importedDoc,
  setImportedDoc,
  docEditorModal,
  setDocEditorModal,
  modelAnswersLoading,
  standardsAlignment,
  alignmentLoading,
  rewriteLoading,
  handleAlignToStandards,
  handleRewriteForAlignment,
  config,
  fileInputRef,
  skipAutoSaveRef,
  loadAssignment,
  deleteAssignment,
  saveAssignmentConfig,
  exportAssignment,
  handleDocImport,
  openDocEditor,
  handleGenerateModelAnswers,
  removeMarker,
  addQuestion,
  updateQuestion,
  removeQuestion,
  addToast,
  getMarkerText,
  getMarkerPoints,
  getMarkerType,
  calculateTotalPoints,
  removeAllHighlightsFromHtml,
  applyAllHighlights,
  textToRichHtml,
  markerLibrary,
}) {
  const [savedAssignmentsExpanded, setSavedAssignmentsExpanded] = useState(false);
  const { openSavedAssignment, toggleCountsTowardsGrade } =
    createSavedAssignmentHandlers({
      setIsLoadingAssignment,
      skipAutoSaveRef,
      setImportedDoc,
      setAssignment,
      setLoadedAssignmentName,
      setDocEditorModal,
      addToast,
      textToRichHtml,
      removeAllHighlightsFromHtml,
      applyAllHighlights,
      savedAssignmentData,
      setSavedAssignmentData,
    });
  return (
    <div data-tutorial="builder-card" className="fade-in">
      {/* Saved Assignments - Collapsible */}
      <SavedAssignmentsCard
        savedAssignments={savedAssignments}
        savedAssignmentData={savedAssignmentData}
        loadedAssignmentName={loadedAssignmentName}
        savedAssignmentsExpanded={savedAssignmentsExpanded}
        setSavedAssignmentsExpanded={setSavedAssignmentsExpanded}
        loadAssignment={loadAssignment}
        deleteAssignment={deleteAssignment}
        openSavedAssignment={openSavedAssignment}
        toggleCountsTowardsGrade={toggleCountsTowardsGrade}
      />

      {/* Assignment Editor */}
      <div className="glass-card" style={{ padding: "30px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "25px",
          }}
        >
          <h2
            style={{
              fontSize: "1.3rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <Icon name="FileEdit" size={24} />
            {assignment.title
              ? `Editing: ${assignment.title}`
              : "New Assignment"}
          </h2>
          {assignment.title && (
            <span
              style={{
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
              }}
            >
              {(assignment.customMarkers || []).length} markers
            </span>
          )}
        </div>

        {/* Assignment Details */}
        <AssignmentDetailsSection
          assignment={assignment}
          setAssignment={setAssignment}
          config={config}
        />

        {/* Due Date & Late Policy */}
        <DueDatePolicySection assignment={assignment} setAssignment={setAssignment} />

        {/* Import Document */}
        <ImportDocumentSection
          assignment={assignment}
          setAssignment={setAssignment}
          importedDoc={importedDoc}
          setImportedDoc={setImportedDoc}
          setLoadedAssignmentName={setLoadedAssignmentName}
          fileInputRef={fileInputRef}
          handleDocImport={handleDocImport}
          openDocEditor={openDocEditor}
          removeMarker={removeMarker}
          getMarkerText={getMarkerText}
          getMarkerPoints={getMarkerPoints}
          getMarkerType={getMarkerType}
          calculateTotalPoints={calculateTotalPoints}
        />

        {/* Marker Library */}
        <MarkerLibrarySection
          assignment={assignment}
          setAssignment={setAssignment}
          config={config}
          markerLibrary={markerLibrary}
        />

        {/* Rubric Type Selector */}
        <RubricTypeSection assignment={assignment} setAssignment={setAssignment} />

        {/* Generate Model Answers */}
        <ModelAnswersSection
          assignment={assignment}
          importedDoc={importedDoc}
          modelAnswersLoading={modelAnswersLoading}
          handleGenerateModelAnswers={handleGenerateModelAnswers}
        />

        {/* Align to Standards */}
        <StandardsAlignmentSection
          importedDoc={importedDoc}
          standardsAlignment={standardsAlignment}
          alignmentLoading={alignmentLoading}
          rewriteLoading={rewriteLoading}
          handleAlignToStandards={handleAlignToStandards}
          handleRewriteForAlignment={handleRewriteForAlignment}
        />

        {/* Grading Notes */}
        <div data-tutorial="builder-notes" style={{ marginBottom: "25px" }}>
          <label className="label">
            Assignment-Specific Grading Notes
          </label>
          <textarea
            className="input"
            value={assignment.gradingNotes}
            onChange={(e) =>
              setAssignment({
                ...assignment,
                gradingNotes: e.target.value,
              })
            }
            placeholder="Special instructions for grading this assignment..."
            style={{ minHeight: "100px" }}
          />
        </div>

        {/* Questions */}
        <QuestionsSection
          assignment={assignment}
          addQuestion={addQuestion}
          updateQuestion={updateQuestion}
          removeQuestion={removeQuestion}
          markerLibrary={markerLibrary}
        />

        {/* Export Buttons */}
        <ExportButtonsSection
          assignment={assignment}
          saveAssignmentConfig={saveAssignmentConfig}
          exportAssignment={exportAssignment}
        />
      </div>
    </div>
  );
});
