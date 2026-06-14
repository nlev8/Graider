import React from "react";
import Icon from "../../components/Icon";
import AssignmentResultsCard from "./AssignmentResultsCard";

/*
 * AssignmentResultsSection — extracted from ResultsTab (CQ wave-3 split).
 * Renders the collapsible "Assignment Results" toggle header and, when open,
 * delegates all interior rendering to AssignmentResultsCard.
 *
 * Pure-prop component: no new state, effects, or fetches. All state and
 * handlers are owned by ResultsTab and passed down as props.
 */
export default function AssignmentResultsSection({
  // Collapsible state (owned by parent ResultsTab)
  assignmentSectionOpen,
  setAssignmentSectionOpen,
  // All remaining props are forwarded to AssignmentResultsCard
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
  setColWidths,
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
    <div>
      <div
        onClick={function() { setAssignmentSectionOpen(!assignmentSectionOpen); }}
        style={{
          display: "flex", alignItems: "center", gap: "10px",
          padding: "12px 16px",
          background: assignmentSectionOpen ? "rgba(255,255,255,0.03)" : "var(--glass-bg)",
          border: "1px solid var(--glass-border)",
          borderRadius: assignmentSectionOpen ? "10px 10px 0 0" : "10px",
          cursor: "pointer",
        }}
      >
        <Icon name={assignmentSectionOpen ? "ChevronDown" : "ChevronRight"} size={16} />
        <span style={{ fontWeight: 700, fontSize: "1rem" }}>Assignment Results</span>
        <span style={{
          padding: "2px 8px", borderRadius: "10px", fontSize: "0.75rem",
          background: "rgba(255,255,255,0.08)", color: "var(--text-secondary)",
        }}>{(status.results || []).length + ' graded'}</span>
      </div>
      {assignmentSectionOpen && (
        <AssignmentResultsCard
          status={status}
          config={config}
          theme={theme}
          resultsPeriodFilter={resultsPeriodFilter}
          setResultsPeriodFilter={setResultsPeriodFilter}
          resultsFilter={resultsFilter}
          setResultsFilter={setResultsFilter}
          resultsAssignmentFilter={resultsAssignmentFilter}
          setResultsAssignmentFilter={setResultsAssignmentFilter}
          resultsSort={resultsSort}
          setResultsSort={setResultsSort}
          resultsSearch={resultsSearch}
          setResultsSearch={setResultsSearch}
          batchExportLoading={batchExportLoading}
          setBatchExportLoading={setBatchExportLoading}
          outlookExportLoading={outlookExportLoading}
          setOutlookExportLoading={setOutlookExportLoading}
          ccParents={ccParents}
          setCcParents={setCcParents}
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
    </div>
  );
}
