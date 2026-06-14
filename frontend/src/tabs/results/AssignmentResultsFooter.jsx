import React from "react";
import PortalSubmissionsSection from "./PortalSubmissionsSection";
import AssignmentResultsBody from "./AssignmentResultsBody";

/*
 * AssignmentResultsFooter — extracted from AssignmentResultsCard (CQ wave-3 split).
 * Renders the email status banner, portal submissions section, and the
 * results body (empty-state OR search + table + send button).
 *
 * Pure-prop component: no new state, effects, or fetches. All state and
 * handlers are owned by ResultsTab and passed down as props.
 */
export default function AssignmentResultsFooter({
  emailStatus,
  setEmailStatus,
  portalSubmissions,
  resultsFilter,
  pendingConfirmations,
  vportalConfigured,
  outlookSendStatus,
  setOutlookSendStatus,
  setOutlookSendPolling,
  addToast,
  pendingConfirmationIds,
  status,
  resultsSearch,
  setResultsSearch,
  editedResults,
  setStatus,
  setEditedResults,
  emailApprovals,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  resultsSort,
  colWidths,
  defaultColPercents,
  tableRef,
  initColWidths,
  handleResizeStart,
  theme,
  studentAccommodations,
  config,
  setConfig,
  autoApproveEmails,
  sentEmails,
  openReview,
  sendSingleEmail,
  editedEmails,
  getDefaultEmailBody,
  setSentEmails,
}) {
  return (
    <>
      {emailStatus.message && (
        <div
          style={{
            marginBottom: "15px",
            padding: "12px 15px",
            background: emailStatus.message.includes("Error")
              ? "rgba(248,113,113,0.1)"
              : "rgba(74,222,128,0.1)",
            borderRadius: "8px",
            border: emailStatus.message.includes("Error")
              ? "1px solid rgba(248,113,113,0.3)"
              : "1px solid rgba(74,222,128,0.3)",
          }}
        >
          {emailStatus.message}
        </div>
      )}

      {/* Portal Submissions Section */}
      <PortalSubmissionsSection
        portalSubmissions={portalSubmissions}
        resultsFilter={resultsFilter}
        pendingConfirmations={pendingConfirmations}
        vportalConfigured={vportalConfigured}
        outlookSendStatus={outlookSendStatus}
        setOutlookSendStatus={setOutlookSendStatus}
        setOutlookSendPolling={setOutlookSendPolling}
        addToast={addToast}
        pendingConfirmationIds={pendingConfirmationIds}
      />

      {/* Results body: empty-state OR search + table + send button */}
      <AssignmentResultsBody
        status={status}
        portalSubmissions={portalSubmissions}
        resultsSearch={resultsSearch}
        setResultsSearch={setResultsSearch}
        editedResults={editedResults}
        setStatus={setStatus}
        setEditedResults={setEditedResults}
        resultsFilter={resultsFilter}
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
        addToast={addToast}
        autoApproveEmails={autoApproveEmails}
        sentEmails={sentEmails}
        outlookSendStatus={outlookSendStatus}
        openReview={openReview}
        sendSingleEmail={sendSingleEmail}
        editedEmails={editedEmails}
        getDefaultEmailBody={getDefaultEmailBody}
        emailStatus={emailStatus}
        setEmailStatus={setEmailStatus}
        setSentEmails={setSentEmails}
      />
    </>
  );
}
