import React from "react";
import ResultsHeader from "./ResultsHeader";
import SendProgressIndicators from "./SendProgressIndicators";
import AuthenticitySummaryAlert from "./AuthenticitySummaryAlert";
import AutoApproveControls from "./AutoApproveControls";
import AssignmentResultsFooter from "./AssignmentResultsFooter";

/*
 * AssignmentResultsCard — extracted from AssignmentResultsSection (CQ wave-3 split).
 * Renders the glass-card interior of the "Assignment Results" collapsible section:
 * filter/export header, progress indicators, authenticity alert, auto-approve
 * controls, and the footer (email banner + portal submissions + results body).
 *
 * Pure-prop component: no new state, effects, or fetches. All state and
 * handlers are owned by ResultsTab and passed down as props.
 */
export default function AssignmentResultsCard({
  status,
  config,
  theme,
  resultsPeriodFilter,
  setResultsPeriodFilter,
  resultsFilter,
  setResultsFilter,
  resultsAssignmentFilter,
  setResultsAssignmentFilter,
  resultsSort,
  setResultsSort,
  resultsSearch,
  setResultsSearch,
  batchExportLoading,
  setBatchExportLoading,
  outlookExportLoading,
  setOutlookExportLoading,
  ccParents,
  setCcParents,
  editedResults,
  emailApprovals,
  sentEmails,
  editedEmails,
  emailStatus,
  autoApproveEmails,
  gradesApproved,
  savedAssignments,
  savedAssignmentData,
  studentAccommodations,
  sortedPeriods,
  portalSubmissions,
  vportalConfigured,
  outlookSendStatus,
  focusCommsStatus,
  focusCommentsStatus,
  curveModal,
  colWidths,
  defaultColPercents,
  pendingConfirmations,
  pendingConfirmationStudents,
  confirmationStudentFilter,
  setStatus,
  setConfig,
  setEditedResults,
  setEmailApprovals,
  setSentEmails,
  setEditedEmails,
  setEmailStatus,
  setAutoApproveEmails,
  setGradesApproved,
  setOutlookSendStatus,
  setOutlookSendPolling,
  setFocusCommsStatus,
  setFocusCommsPolling,
  setFocusCommentsStatus,
  setFocusCommentsPolling,
  setCurveModal,
  setFocusExportModal,
  setConfirmationStudentFilter,
  addToast,
  openReview,
  sendSingleEmail,
  getDefaultEmailBody,
  updateApprovalsBulk,
  initColWidths,
  handleResizeStart,
  tableRef,
  pendingConfirmationIds,
  pendingConfirmationFilenames,
}) {
  return (
    <div data-tutorial="results-card" className="glass-card" style={{ padding: "25px" }}>
      <ResultsHeader
        status={status}
        resultsFilter={resultsFilter}
        resultsPeriodFilter={resultsPeriodFilter}
        resultsAssignmentFilter={resultsAssignmentFilter}
        emailApprovals={emailApprovals}
        resultsSort={resultsSort}
        setResultsSort={setResultsSort}
        setResultsFilter={setResultsFilter}
        portalSubmissions={portalSubmissions}
        sortedPeriods={sortedPeriods}
        setResultsPeriodFilter={setResultsPeriodFilter}
        savedAssignments={savedAssignments}
        savedAssignmentData={savedAssignmentData}
        setResultsAssignmentFilter={setResultsAssignmentFilter}
        curveModal={curveModal}
        setCurveModal={setCurveModal}
        resultsSearch={resultsSearch}
        setStatus={setStatus}
        setEditedResults={setEditedResults}
        setEmailApprovals={setEmailApprovals}
        setEditedEmails={setEditedEmails}
        addToast={addToast}
        gradesApproved={gradesApproved}
        setGradesApproved={setGradesApproved}
        batchExportLoading={batchExportLoading}
        setBatchExportLoading={setBatchExportLoading}
        editedResults={editedResults}
        setFocusExportModal={setFocusExportModal}
        config={config}
        focusCommentsStatus={focusCommentsStatus}
        setFocusCommentsStatus={setFocusCommentsStatus}
        setFocusCommentsPolling={setFocusCommentsPolling}
        vportalConfigured={vportalConfigured}
        outlookExportLoading={outlookExportLoading}
        setOutlookExportLoading={setOutlookExportLoading}
        outlookSendStatus={outlookSendStatus}
        setOutlookSendStatus={setOutlookSendStatus}
        setOutlookSendPolling={setOutlookSendPolling}
        focusCommsStatus={focusCommsStatus}
        setFocusCommsStatus={setFocusCommsStatus}
        setFocusCommsPolling={setFocusCommsPolling}
        setConfirmationStudentFilter={setConfirmationStudentFilter}
        confirmationStudentFilter={confirmationStudentFilter}
        pendingConfirmationStudents={pendingConfirmationStudents}
        pendingConfirmations={pendingConfirmations}
        pendingConfirmationFilenames={pendingConfirmationFilenames}
        ccParents={ccParents}
        setCcParents={setCcParents}
      />

      {/* Outlook Send Progress */}
      <SendProgressIndicators
        outlookSendStatus={outlookSendStatus}
        focusCommsStatus={focusCommsStatus}
      />

      {/* Authenticity Summary Alert */}
      <AuthenticitySummaryAlert status={status} />

      {/* Auto-Approve Toggle */}
      <AutoApproveControls
        status={status}
        autoApproveEmails={autoApproveEmails}
        setAutoApproveEmails={setAutoApproveEmails}
        resultsFilter={resultsFilter}
        resultsPeriodFilter={resultsPeriodFilter}
        resultsAssignmentFilter={resultsAssignmentFilter}
        emailApprovals={emailApprovals}
        updateApprovalsBulk={updateApprovalsBulk}
        sentEmails={sentEmails}
        setSentEmails={setSentEmails}
        addToast={addToast}
      />

      {/* Email banner + portal submissions + results body */}
      <AssignmentResultsFooter
        emailStatus={emailStatus}
        setEmailStatus={setEmailStatus}
        portalSubmissions={portalSubmissions}
        resultsFilter={resultsFilter}
        pendingConfirmations={pendingConfirmations}
        vportalConfigured={vportalConfigured}
        outlookSendStatus={outlookSendStatus}
        setOutlookSendStatus={setOutlookSendStatus}
        setOutlookSendPolling={setOutlookSendPolling}
        addToast={addToast}
        pendingConfirmationIds={pendingConfirmationIds}
        status={status}
        resultsSearch={resultsSearch}
        setResultsSearch={setResultsSearch}
        editedResults={editedResults}
        setStatus={setStatus}
        setEditedResults={setEditedResults}
        emailApprovals={emailApprovals}
        resultsPeriodFilter={resultsPeriodFilter}
        resultsAssignmentFilter={resultsAssignmentFilter}
        resultsSort={resultsSort}
        colWidths={colWidths}
        defaultColPercents={defaultColPercents}
        tableRef={tableRef}
        initColWidths={initColWidths}
        handleResizeStart={handleResizeStart}
        theme={theme}
        studentAccommodations={studentAccommodations}
        config={config}
        setConfig={setConfig}
        autoApproveEmails={autoApproveEmails}
        sentEmails={sentEmails}
        openReview={openReview}
        sendSingleEmail={sendSingleEmail}
        editedEmails={editedEmails}
        getDefaultEmailBody={getDefaultEmailBody}
        setSentEmails={setSentEmails}
      />
    </div>
  );
}
