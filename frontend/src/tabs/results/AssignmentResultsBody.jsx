import React from "react";
import ResultsTable, { ResultsSearchInput } from "./ResultsTable";
import SendApprovedEmailsButton from "./SendApprovedEmailsButton";

/*
 * AssignmentResultsBody — extracted from AssignmentResultsSection (CQ wave-3 split).
 * Renders the empty-state fallback OR the search input + results table + send button.
 *
 * Pure-prop component: no new state, effects, or fetches. All state and
 * handlers are owned by ResultsTab and passed down as props.
 */
export default function AssignmentResultsBody({
  status,
  portalSubmissions,
  resultsSearch,
  setResultsSearch,
  editedResults,
  setStatus,
  setEditedResults,
  resultsFilter,
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
  addToast,
  autoApproveEmails,
  sentEmails,
  outlookSendStatus,
  openReview,
  sendSingleEmail,
  editedEmails,
  getDefaultEmailBody,
  emailStatus,
  setEmailStatus,
  setSentEmails,
}) {
  if (status.results.length === 0 && portalSubmissions.length === 0) {
    return (
      <p
        style={{
          color: "var(--text-secondary)",
          textAlign: "center",
          padding: "40px",
        }}
      >
        No results yet. Grade some assignments first.
      </p>
    );
  }
  return (
    <>
      {/* Search Input */}
      <ResultsSearchInput
        resultsSearch={resultsSearch}
        setResultsSearch={setResultsSearch}
      />
      <ResultsTable
        editedResults={editedResults}
        status={status}
        setStatus={setStatus}
        setEditedResults={setEditedResults}
        resultsFilter={resultsFilter}
        emailApprovals={emailApprovals}
        resultsPeriodFilter={resultsPeriodFilter}
        resultsAssignmentFilter={resultsAssignmentFilter}
        resultsSearch={resultsSearch}
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
      />

      {/* Send Approved Emails Button */}
      <SendApprovedEmailsButton
        emailApprovals={emailApprovals}
        autoApproveEmails={autoApproveEmails}
        status={status}
        editedEmails={editedEmails}
        getDefaultEmailBody={getDefaultEmailBody}
        emailStatus={emailStatus}
        setEmailStatus={setEmailStatus}
        sentEmails={sentEmails}
        setSentEmails={setSentEmails}
        config={config}
      />
    </>
  );
}
