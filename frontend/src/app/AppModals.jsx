import React from "react";
import OnboardingWizard from "../components/OnboardingWizard";
import TutorialOverlay, { TUTORIAL_STEPS } from "../components/TutorialOverlay";
import EmailPreviewModal from "../components/EmailPreviewModal";
import ReviewModal from "../components/ReviewModal";
import DocumentEditorModal from "../components/DocumentEditorModal";
import { getMarkerText, getEndMarker } from "../utils/markerHelpers";
import { removeAllHighlightsFromHtml } from "../utils/htmlHighlight";
import { HIGHLIGHT_COLORS } from "./appConstants";

/*
 * AppModals — the top-of-tree overlay mounts (OnboardingWizard,
 * TutorialOverlay, EmailPreviewModal, ReviewModal, DocumentEditorModal),
 * relocated VERBATIM from App.jsx 1968-2070 in the finale split
 * (PlannerModals/SettingsModals aggregator precedent). Stateless: every
 * mount keeps its original `{cond && ...}` guard, and these five mounts were
 * the FIRST children of App's root div, so a fragment in the same position
 * preserves DOM/stacking order exactly. FocusExportModal, CurveModal and
 * ToastStack are NOT here — they render after the layout in App.jsx, and
 * folding them in would reorder siblings.
 */
export default function AppModals(props) {
  const {
    addSelectedAsMarker, addToast, apiKeys, applyAllHighlights, assignment, autoApproveEmails,
    config, docEditorModal, docHtmlRef, editedEmails, editedResults, emailApprovals, emailPreview,
    highlighterMode, importedDoc, removeMarker, reviewModal, reviewModalRightTab, reviewModalTab,
    rubric, sendEmails, sentEmails, setActiveTab, setApiKeys, setAssignment, setConfig,
    setDocEditorModal, setEditedEmails, setEmailPreview, setHighlighterMode, setImportedDoc,
    setLoadedAssignmentName, setPlannerMode, setReviewModal, setReviewModalRightTab,
    setReviewModalTab, setRubric, setSavedAssignmentData, setSavedAssignments, setSentEmails,
    setSettingsTab, setShowAIReasoning, setShowOnboardingWizard, setShowTutorial, setStatus,
    setTutorialStep, showAIReasoning, showOnboardingWizard, showTutorial, status, theme,
    toggleTheme, tutorialStep, updateApprovalStatus, updateGrade, user,
  } = props;

  return (
    <>
      {/* AI notice moved to OnboardingWizard */}
      {/* Onboarding Wizard */}
      {showOnboardingWizard && (
        <OnboardingWizard
          config={config}
          setConfig={setConfig}
          rubric={rubric}
          setRubric={setRubric}
          apiKeys={apiKeys}
          setApiKeys={setApiKeys}
          user={user}
          onComplete={(navigateTo) => {
            setShowOnboardingWizard(false);
            if (navigateTo === "builder") setActiveTab("builder");
            if (!localStorage.getItem("graider-tutorial-complete")) {
              setTutorialStep(0);
              setShowTutorial(true);
            }
          }}
          addToast={addToast}
          theme={theme}
          toggleTheme={toggleTheme}
        />
      )}

      {/* Tutorial Overlay */}
      {showTutorial && (
        <TutorialOverlay
          currentStep={tutorialStep}
          onNext={() => setTutorialStep((s) => Math.min(s + 1, TUTORIAL_STEPS.length - 1))}
          onBack={() => setTutorialStep((s) => Math.max(s - 1, 0))}
          onSkip={() => {
            setShowTutorial(false);
            setTutorialStep(0);
            localStorage.setItem("graider-tutorial-complete", "true");
          }}
          setActiveTab={setActiveTab}
          setSettingsTab={setSettingsTab}
          setPlannerMode={setPlannerMode}
        />
      )}

      {/* Email Preview Modal */}
      {emailPreview.show && (
        <EmailPreviewModal
          emailPreview={emailPreview}
          sendEmails={sendEmails}
          setEmailPreview={setEmailPreview}
        />
      )}

      {/* Review Modal - Full Screen */}
      {reviewModal.show && reviewModal.index >= 0 && (
        <ReviewModal
          addToast={addToast}
          autoApproveEmails={autoApproveEmails}
          config={config}
          editedEmails={editedEmails}
          editedResults={editedResults}
          emailApprovals={emailApprovals}
          reviewModal={reviewModal}
          reviewModalRightTab={reviewModalRightTab}
          reviewModalTab={reviewModalTab}
          sentEmails={sentEmails}
          setEditedEmails={setEditedEmails}
          setReviewModal={setReviewModal}
          setReviewModalRightTab={setReviewModalRightTab}
          setReviewModalTab={setReviewModalTab}
          setSentEmails={setSentEmails}
          setShowAIReasoning={setShowAIReasoning}
          setStatus={setStatus}
          showAIReasoning={showAIReasoning}
          status={status}
          updateApprovalStatus={updateApprovalStatus}
          updateGrade={updateGrade}
        />
      )}

      {/* Document Editor Modal */}
      {docEditorModal.show && (
        <DocumentEditorModal
          HIGHLIGHT_COLORS={HIGHLIGHT_COLORS}
          addSelectedAsMarker={addSelectedAsMarker}
          addToast={addToast}
          applyAllHighlights={applyAllHighlights}
          assignment={assignment}
          docEditorModal={docEditorModal}
          docHtmlRef={docHtmlRef}
          getEndMarker={getEndMarker}
          getMarkerText={getMarkerText}
          highlighterMode={highlighterMode}
          importedDoc={importedDoc}
          removeAllHighlightsFromHtml={removeAllHighlightsFromHtml}
          removeMarker={removeMarker}
          setAssignment={setAssignment}
          setDocEditorModal={setDocEditorModal}
          setHighlighterMode={setHighlighterMode}
          setImportedDoc={setImportedDoc}
          setLoadedAssignmentName={setLoadedAssignmentName}
          setSavedAssignmentData={setSavedAssignmentData}
          setSavedAssignments={setSavedAssignments}
        />
      )}
    </>
  );
}
