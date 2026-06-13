import React, { Suspense } from "react";
import GradeTab from "../tabs/GradeTab";
import ResultsTab from "../tabs/ResultsTab";
import SettingsTab from "../tabs/SettingsTab";
import BuilderTab from "../tabs/BuilderTab";
import PlannerTab from "../tabs/PlannerTab";
import HelpTab from "../components/HelpTab";
import AssistantChat from "../components/AssistantChat";
import AutomationBuilder from "../components/AutomationBuilder";
import BehaviorPanel from "../components/BehaviorPanel";
import { getMarkerText, getMarkerPoints, getMarkerType, calculateTotalPoints } from "../utils/markerHelpers";
import { removeAllHighlightsFromHtml, textToRichHtml } from "../utils/htmlHighlight";
import { getSubjectSectionDefaults, distributeDOK, distributePoints } from "../utils/assessmentDistribution";
import { markerLibrary, EDTECH_TOOLS, MODEL_COST_PER_ASSIGNMENT, defaultColPercents } from "./appConstants";
// React.lazy declarations moved verbatim from App.jsx 91-92 with the tab
// mounts that consume them (lazy() is module-scope either way).
const AnalyticsTab = React.lazy(() => import("../tabs/AnalyticsTab"));
var AdminTab = React.lazy(function() { return import("../tabs/AdminTab"); });

/*
 * AppTabPanels — the tab-switching content block, relocated VERBATIM from
 * App.jsx 2171-2539 in the finale split. Split into two sibling fragments
 * (PrimaryTabPanels: grade/results/help/settings/automations/assistant/
 * builder; StudioTabPanels: analytics/admin/planner) purely to keep every
 * function ≤300 LOC — fragments add no DOM nodes, so the rendered tree and
 * sibling order are exactly the pre-split ones. The always-mounted
 * display:none Grade/Assistant/Planner panels keep their precedent
 * (state persists across tab switches); data-tutorial anchors unchanged.
 */
function PrimaryTabPanels(props) {
  const {
    accommodationPresets, activeTab, addQuestion, addToast, apiKeys, applyAllHighlights,
    assessmentResults, assessmentTemplates, assignment, autoApproveEmails, colWidths, config,
    confirmationStudentFilter, curveModal, deleteAssignment, docEditorModal, editedEmails,
    editedResults, emailApprovals, emailStatus, exportAssignment, fileInputRef,
    focusCommentsStatus, focusCommsStatus, getDefaultEmailBody, globalAINotes, gradesApproved,
    handleDocImport, handleGenerateModelAnswers, handleResizeStart, importedDoc, initColWidths,
    isLoadingAssignment, loadAssignment, loadedAssignmentName, modelAnswersLoading, openDocEditor,
    openReview, outlookSendStatus, pendingConfirmationFilenames, pendingConfirmationIds,
    pendingConfirmationStudents, pendingConfirmations, periods, portalSubmissions, removeMarker,
    removeQuestion, resultsPeriodFilter, rosters, rubric, saveAssignmentConfig,
    savedAssignmentData, savedAssignments, sendSingleEmail, sentEmails, setApiKeys,
    setAssessmentResults, setAssessmentTemplates, setAssignment, setAutoApproveEmails,
    setColWidths, setConfig, setConfirmationStudentFilter, setCurveModal, setDocEditorModal,
    setEditedEmails, setEditedResults, setEmailApprovals, setEmailStatus, setFocusCommentsPolling,
    setFocusCommentsStatus, setFocusCommsPolling, setFocusCommsStatus, setFocusExportModal,
    setGlobalAINotes, setGradesApproved, setImportedDoc, setIsLoadingAssignment,
    setLoadedAssignmentName, setOutlookSendPolling, setOutlookSendStatus, setPeriods,
    setResultsPeriodFilter, setRosters, setRubric, setSavedAssignmentData, setSentEmails,
    setSettingsTab, setShowOnboardingWizard, setShowTutorial, setStatus, setStudentAccommodations,
    setSubscription, setSubscriptionLoading, setSupportDocs, setTutorialStep, setUploadingTemplate,
    setVportalConfigured, setVportalEmail, settingsTab, showOnboardingWizard, skipAutoSaveRef,
    sortedPeriods, status, studentAccommodations, subscription, subscriptionLoading, supportDocs,
    tableRef, theme, updateApprovalsBulk, updateQuestion, uploadingTemplate, vportalConfigured,
    vportalEmail,
  } = props;
  return (
    <>
              {/* Grade Tab — always-mounted with display:none so state persists across tab switches.
                  Same precedent as the Assistant tab below at App.jsx:9306-9317.
                  Required before PR 2 moves Grade-specific state into GradeTab — conditional
                  mount + local state would reset state on every tab switch. */}
              <div style={{ display: activeTab === "grade" ? "block" : "none" }}>
                <GradeTab
                  status={status}
                  setStatus={setStatus}
                  config={config}
                  globalAINotes={globalAINotes}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  addToast={addToast}
                  periods={periods}
                  sortedPeriods={sortedPeriods}
                  emailApprovals={emailApprovals}
                />
              </div>

              {/* Results Tab */}
              {activeTab === "results" && (
                <ResultsTab
                  status={status}
                  config={config}
                  rubric={rubric}
                  globalAINotes={globalAINotes}
                  theme={theme}
                  resultsPeriodFilter={resultsPeriodFilter}
                  editedResults={editedResults}
                  emailApprovals={emailApprovals}
                  sentEmails={sentEmails}
                  editedEmails={editedEmails}
                  emailStatus={emailStatus}
                  autoApproveEmails={autoApproveEmails}
                  gradesApproved={gradesApproved}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  studentAccommodations={studentAccommodations}
                  sortedPeriods={sortedPeriods}
                  portalSubmissions={portalSubmissions}
                  assessmentResults={assessmentResults}
                  setAssessmentResults={setAssessmentResults}
                  vportalConfigured={vportalConfigured}
                  outlookSendStatus={outlookSendStatus}
                  focusCommsStatus={focusCommsStatus}
                  focusCommentsStatus={focusCommentsStatus}
                  curveModal={curveModal}
                  colWidths={colWidths}
                  defaultColPercents={defaultColPercents}
                  pendingConfirmations={pendingConfirmations}
                  pendingConfirmationStudents={pendingConfirmationStudents}
                  confirmationStudentFilter={confirmationStudentFilter}
                  setResultsPeriodFilter={setResultsPeriodFilter}
                  setStatus={setStatus}
                  setConfig={setConfig}
                  setEditedResults={setEditedResults}
                  setEmailApprovals={setEmailApprovals}
                  setSentEmails={setSentEmails}
                  setEditedEmails={setEditedEmails}
                  setEmailStatus={setEmailStatus}
                  setAutoApproveEmails={setAutoApproveEmails}
                  setGradesApproved={setGradesApproved}
                  setOutlookSendStatus={setOutlookSendStatus}
                  setOutlookSendPolling={setOutlookSendPolling}
                  setFocusCommsStatus={setFocusCommsStatus}
                  setFocusCommsPolling={setFocusCommsPolling}
                  setFocusCommentsStatus={setFocusCommentsStatus}
                  setFocusCommentsPolling={setFocusCommentsPolling}
                  setCurveModal={setCurveModal}
                  setFocusExportModal={setFocusExportModal}
                  setColWidths={setColWidths}
                  setConfirmationStudentFilter={setConfirmationStudentFilter}
                  addToast={addToast}
                  openReview={openReview}
                  sendSingleEmail={sendSingleEmail}
                  getDefaultEmailBody={getDefaultEmailBody}
                  updateApprovalsBulk={updateApprovalsBulk}
                  initColWidths={initColWidths}
                  handleResizeStart={handleResizeStart}
                  tableRef={tableRef}
                  pendingConfirmationIds={pendingConfirmationIds}
                  pendingConfirmationFilenames={pendingConfirmationFilenames}
                />
              )}

              {/* Help Tab */}
              <HelpTab activeTab={activeTab} setShowTutorial={setShowTutorial} setTutorialStep={setTutorialStep} />

              {/* Settings Tab */}
              {activeTab === "settings" && (
                <SettingsTab
                  settingsTab={settingsTab}
                  setSettingsTab={setSettingsTab}
                  config={config}
                  setConfig={setConfig}
                  rubric={rubric}
                  setRubric={setRubric}
                  globalAINotes={globalAINotes}
                  setGlobalAINotes={setGlobalAINotes}
                  apiKeys={apiKeys}
                  setApiKeys={setApiKeys}
                  subscription={subscription}
                  setSubscription={setSubscription}
                  subscriptionLoading={subscriptionLoading}
                  setSubscriptionLoading={setSubscriptionLoading}
                  periods={periods}
                  setPeriods={setPeriods}
                  rosters={rosters}
                  setRosters={setRosters}
                  studentAccommodations={studentAccommodations}
                  setStudentAccommodations={setStudentAccommodations}
                  vportalEmail={vportalEmail}
                  setVportalEmail={setVportalEmail}
                  vportalConfigured={vportalConfigured}
                  setVportalConfigured={setVportalConfigured}
                  supportDocs={supportDocs}
                  setSupportDocs={setSupportDocs}
                  assessmentTemplates={assessmentTemplates}
                  setAssessmentTemplates={setAssessmentTemplates}
                  uploadingTemplate={uploadingTemplate}
                  setUploadingTemplate={setUploadingTemplate}
                  showOnboardingWizard={showOnboardingWizard}
                  setShowOnboardingWizard={setShowOnboardingWizard}
                  sortedPeriods={sortedPeriods}
                  accommodationPresets={accommodationPresets}
                  EDTECH_TOOLS={EDTECH_TOOLS}
                  MODEL_COST_PER_ASSIGNMENT={MODEL_COST_PER_ASSIGNMENT}
                  addToast={addToast}
                />
              )}

              {/* Script Builder / Automations Tab */}
              {activeTab === "automations" && (
                <div className="fade-in glass-card" style={{ padding: "25px" }}>
                  <AutomationBuilder addToast={addToast} />
                </div>
              )}

              {/* Assistant Tab — always mounted so chat persists across tab switches */}
              <div data-tutorial="assistant-chat" className={activeTab === "assistant" ? "fade-in glass-card" : ""} style={{
                padding: 0,
                overflow: "hidden",
                display: activeTab === "assistant" ? "flex" : "none",
                position: "relative",
              }}>
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                  <AssistantChat addToast={addToast} subject={config.subject} />
                </div>
                {window.location.hostname === 'localhost' && <BehaviorPanel addToast={addToast} />}
              </div>

              {/* Builder Tab */}
              {activeTab === "builder" && (
                <BuilderTab
                  assignment={assignment}
                  setAssignment={setAssignment}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  loadedAssignmentName={loadedAssignmentName}
                  setLoadedAssignmentName={setLoadedAssignmentName}
                  isLoadingAssignment={isLoadingAssignment}
                  setIsLoadingAssignment={setIsLoadingAssignment}
                  importedDoc={importedDoc}
                  setImportedDoc={setImportedDoc}
                  docEditorModal={docEditorModal}
                  setDocEditorModal={setDocEditorModal}
                  modelAnswersLoading={modelAnswersLoading}
                  config={config}
                  fileInputRef={fileInputRef}
                  skipAutoSaveRef={skipAutoSaveRef}
                  loadAssignment={loadAssignment}
                  deleteAssignment={deleteAssignment}
                  saveAssignmentConfig={saveAssignmentConfig}
                  exportAssignment={exportAssignment}
                  handleDocImport={handleDocImport}
                  openDocEditor={openDocEditor}
                  handleGenerateModelAnswers={handleGenerateModelAnswers}
                  removeMarker={removeMarker}
                  addQuestion={addQuestion}
                  updateQuestion={updateQuestion}
                  removeQuestion={removeQuestion}
                  addToast={addToast}
                  getMarkerText={getMarkerText}
                  getMarkerPoints={getMarkerPoints}
                  getMarkerType={getMarkerType}
                  calculateTotalPoints={calculateTotalPoints}
                  removeAllHighlightsFromHtml={removeAllHighlightsFromHtml}
                  applyAllHighlights={applyAllHighlights}
                  textToRichHtml={textToRichHtml}
                  markerLibrary={markerLibrary}
                />
              )}
    </>
  );
}

function StudioTabPanels(props) {
  const {
    activeTab, addToast, adminSchool, allTeacherTags, assessmentAnswers, assessmentConfig,
    assessmentGradingResults, assessmentLoading, assessmentResults, assessmentStandardsScrollRef,
    assessmentTemplates, config, contentOnly, contentSubmissionsGroups, deletePublishedAssessment,
    deleteSavedAssessment, distributeQuestions, domainNameMap, exportAssessmentForPlatformHandler,
    exportAssessmentHandler, exportLessonPlanHandler, fetchAssessmentResults,
    fetchPublishedAssessments, fetchSavedAssessments, fetchSavedLessons, fetchSharedResources,
    fetchTeacherClasses, fetchTeacherTags, generateAssessmentHandler, generatedAssessment,
    generatedAssignment, getActiveAssignment, getDomains, getTotalQuestionCount, globalAINotes,
    gradeAssessmentAnswersHandler, gradingAssessment, handleDeleteAllSharedResources,
    handleDeleteSharedResource, inProgressDrafts, isAdmin, itemMatchesTagFilter, lessonPlan,
    loadAssignment, loadSavedAssessment, loadingPublished, loadingResults, loadingSavedAssessments,
    loadingSharedResources, periods, plannerMode, publishedAssessments, redistributePoints, rubric,
    saveAssessmentHandler, saveAssessmentName, saveAssignmentConfig, savedAssessments,
    savedAssignmentData, savedAssignments, savedLessons, savingAssessment, scrollToDomain,
    selectedAssessmentResults, selectedSources, selectedStandards, selectedTagFilter,
    setActiveAssignment, setActiveTab, setAllTeacherTags, setAssessmentAnswers,
    setAssessmentConfig, setAssessmentGradingResults, setAssessmentLoading, setAssessmentTemplates,
    setAssignment, setConfig, setContentOnly, setContentSubmissionsGroups, setGeneratedAssessment,
    setGeneratedAssignment, setGlobalAINotes, setGradingAssessment, setInProgressDrafts,
    setLessonPlan, setLoadedAssignmentName, setLoadingPublished, setLoadingResults,
    setLoadingSavedAssessments, setLoadingSharedResources, setPeriods, setPlannerMode,
    setPublishedAssessments, setRubric, setSaveAssessmentName, setSavedAssessments,
    setSavedAssignmentData, setSavedAssignments, setSavedLessons, setSavingAssessment,
    setSelectedAssessmentResults, setSelectedSources, setSelectedStandards, setSelectedTagFilter,
    setSharedResources, setStandards, setStatus, setSupportDocs, setTeacherClasses, setUnitConfig,
    setUploadedDocs, setUploadingTemplate, sharedResources, sortedPeriods, standards,
    standardsScrollRef, status, studentAccommodations, supportDocs, teacherClasses,
    toggleAssessmentStatus, toggleStandard, unitConfig, uploadedDocs, uploadingTemplate, user,
  } = props;
  return (
    <>
              {/* Analytics Tab */}
              {activeTab === "analytics" && (
                <Suspense fallback={
                  <div className="glass-card" style={{ padding: "80px", textAlign: "center" }}>
                    <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>Loading Analytics...</h2>
                  </div>
                }>
                  <AnalyticsTab
                    config={config}
                    status={status}
                    periods={periods}
                    sortedPeriods={sortedPeriods}
                    savedAssignments={savedAssignments}
                    savedAssignmentData={savedAssignmentData}
                    addToast={addToast}
                    assessmentResults={assessmentResults}
                    teacherClasses={teacherClasses}
                  />
                </Suspense>
              )}

              {/* Admin Tab */}
              {activeTab === "admin" && isAdmin && (
                <Suspense fallback={
                  <div className="glass-card" style={{ padding: "80px", textAlign: "center" }}>
                    <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>Loading Admin...</h2>
                  </div>
                }>
                  <AdminTab school={adminSchool} />
                </Suspense>
              )}

              {/* Planner Tab — extracted into tabs/PlannerTab.jsx in PR 1
                  of the Planner tab extraction sprint (plan
                  docs/superpowers/plans/2026-05-04-planner-tab-extraction.md).
                  PR 2 converted to always-mounted with display:none style —
                  same precedent as Assistant tab (App.jsx:7497-7508) and
                  Grade tab (App.jsx:7074). PR 3 moved the calendar slice
                  (calendarData + 14 calendar UI states + 11 calendar
                  helpers + 2 calendar useEffects) into PlannerTab.
                  `plannerMode` stays here so TutorialOverlay (rendered at
                  the App level) can flip Planner sub-modes during tutorial
                  steps without a request/response bridge. */}
              <div style={{ display: activeTab === "planner" ? "block" : "none" }}>
                <PlannerTab
                  status={status}
                  setStatus={setStatus}
                  config={config}
                  setConfig={setConfig}
                  user={user}
                  activeTab={activeTab}
                  addToast={addToast}
                  studentAccommodations={studentAccommodations}
                  lessonPlan={lessonPlan}
                  setLessonPlan={setLessonPlan}
                  generatedAssignment={generatedAssignment}
                  setGeneratedAssignment={setGeneratedAssignment}
                  assessmentConfig={assessmentConfig}
                  setAssessmentConfig={setAssessmentConfig}
                  selectedStandards={selectedStandards}
                  setSelectedStandards={setSelectedStandards}
                  unitConfig={unitConfig}
                  setUnitConfig={setUnitConfig}
                  standards={standards}
                  setStandards={setStandards}
                  setAssignment={setAssignment}
                  uploadedDocs={uploadedDocs}
                  setUploadedDocs={setUploadedDocs}
                  generatedAssessment={generatedAssessment}
                  setGeneratedAssessment={setGeneratedAssessment}
                  rubric={rubric}
                  setRubric={setRubric}
                  globalAINotes={globalAINotes}
                  setGlobalAINotes={setGlobalAINotes}
                  supportDocs={supportDocs}
                  setSupportDocs={setSupportDocs}
                  savedAssignments={savedAssignments}
                  setSavedAssignments={setSavedAssignments}
                  teacherClasses={teacherClasses}
                  setTeacherClasses={setTeacherClasses}
                  periods={periods}
                  setPeriods={setPeriods}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  contentOnly={contentOnly}
                  setContentOnly={setContentOnly}
                  assessmentTemplates={assessmentTemplates}
                  setAssessmentTemplates={setAssessmentTemplates}
                  uploadingTemplate={uploadingTemplate}
                  setUploadingTemplate={setUploadingTemplate}
                  plannerMode={plannerMode}
                  setPlannerMode={setPlannerMode}
                  assessmentLoading={assessmentLoading}
                  setAssessmentLoading={setAssessmentLoading}
                  gradingAssessment={gradingAssessment}
                  setGradingAssessment={setGradingAssessment}
                  savingAssessment={savingAssessment}
                  setSavingAssessment={setSavingAssessment}
                  saveAssessmentName={saveAssessmentName}
                  setSaveAssessmentName={setSaveAssessmentName}
                  assessmentAnswers={assessmentAnswers}
                  setAssessmentAnswers={setAssessmentAnswers}
                  assessmentGradingResults={assessmentGradingResults}
                  setAssessmentGradingResults={setAssessmentGradingResults}
                  selectedSources={selectedSources}
                  setSelectedSources={setSelectedSources}
                  selectedAssessmentResults={selectedAssessmentResults}
                  setSelectedAssessmentResults={setSelectedAssessmentResults}
                  publishedAssessments={publishedAssessments}
                  setPublishedAssessments={setPublishedAssessments}
                  loadingPublished={loadingPublished}
                  setLoadingPublished={setLoadingPublished}
                  inProgressDrafts={inProgressDrafts}
                  setInProgressDrafts={setInProgressDrafts}
                  loadingResults={loadingResults}
                  setLoadingResults={setLoadingResults}
                  sharedResources={sharedResources}
                  setSharedResources={setSharedResources}
                  loadingSharedResources={loadingSharedResources}
                  setLoadingSharedResources={setLoadingSharedResources}
                  contentSubmissionsGroups={contentSubmissionsGroups}
                  setContentSubmissionsGroups={setContentSubmissionsGroups}
                  savedAssessments={savedAssessments}
                  setSavedAssessments={setSavedAssessments}
                  loadingSavedAssessments={loadingSavedAssessments}
                  setLoadingSavedAssessments={setLoadingSavedAssessments}
                  savedLessons={savedLessons}
                  setSavedLessons={setSavedLessons}
                  allTeacherTags={allTeacherTags}
                  setAllTeacherTags={setAllTeacherTags}
                  selectedTagFilter={selectedTagFilter}
                  setSelectedTagFilter={setSelectedTagFilter}
                  loadAssignment={loadAssignment}
                  saveAssignmentConfig={saveAssignmentConfig}
                  domainNameMap={domainNameMap}
                  getDomains={getDomains}
                  scrollToDomain={scrollToDomain}
                  toggleStandard={toggleStandard}
                  standardsScrollRef={standardsScrollRef}
                  assessmentStandardsScrollRef={assessmentStandardsScrollRef}
                  deleteSavedAssessment={deleteSavedAssessment}
                  loadSavedAssessment={loadSavedAssessment}
                  saveAssessmentHandler={saveAssessmentHandler}
                  generateAssessmentHandler={generateAssessmentHandler}
                  gradeAssessmentAnswersHandler={gradeAssessmentAnswersHandler}
                  exportAssessmentHandler={exportAssessmentHandler}
                  exportAssessmentForPlatformHandler={exportAssessmentForPlatformHandler}
                  deletePublishedAssessment={deletePublishedAssessment}
                  toggleAssessmentStatus={toggleAssessmentStatus}
                  fetchAssessmentResults={fetchAssessmentResults}
                  fetchPublishedAssessments={fetchPublishedAssessments}
                  fetchSavedAssessments={fetchSavedAssessments}
                  fetchSavedLessons={fetchSavedLessons}
                  fetchSharedResources={fetchSharedResources}
                  fetchTeacherClasses={fetchTeacherClasses}
                  fetchTeacherTags={fetchTeacherTags}
                  handleDeleteAllSharedResources={handleDeleteAllSharedResources}
                  handleDeleteSharedResource={handleDeleteSharedResource}
                  getActiveAssignment={getActiveAssignment}
                  setActiveAssignment={setActiveAssignment}
                  getTotalQuestionCount={getTotalQuestionCount}
                  distributeDOK={distributeDOK}
                  distributePoints={distributePoints}
                  distributeQuestions={distributeQuestions}
                  redistributePoints={redistributePoints}
                  exportLessonPlanHandler={exportLessonPlanHandler}
                  getSubjectSectionDefaults={getSubjectSectionDefaults}
                  itemMatchesTagFilter={itemMatchesTagFilter}
                  setActiveTab={setActiveTab}
                  setLoadedAssignmentName={setLoadedAssignmentName}
                />
              </div>
    </>
  );
}

export default function AppTabPanels(props) {
  return (
    <>
      <PrimaryTabPanels {...props} />
      <StudioTabPanels {...props} />
    </>
  );
}
