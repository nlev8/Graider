import React, { useState } from "react";
import Icon from "../components/Icon";
import AssessmentResultsSection from "./results/AssessmentResultsSection";
import ResultsHeader from "./results/ResultsHeader";
import SendProgressIndicators from "./results/SendProgressIndicators";
import AuthenticitySummaryAlert from "./results/AuthenticitySummaryAlert";
import AutoApproveControls from "./results/AutoApproveControls";
import PortalSubmissionsSection from "./results/PortalSubmissionsSection";
import ResultsTable, { ResultsSearchInput } from "./results/ResultsTable";
import SendApprovedEmailsButton from "./results/SendApprovedEmailsButton";

/*
 * Props required by ResultsTab:
 *
 * NOTE: The tab's sections are composed from ./results/* (CQ wave-1 split,
 *       behavior-preserving): AssessmentResultsSection, ResultsHeader
 *       (filter/export controls), SendProgressIndicators,
 *       AuthenticitySummaryAlert, AutoApproveControls,
 *       PortalSubmissionsSection, ResultsTable (+Row/cells),
 *       SendApprovedEmailsButton.
 *
 * NOTE: resultsFilter / resultsAssignmentFilter / resultsSort / resultsSearch /
 *       batchExportLoading / outlookExportLoading / ccParents (and their setters) are now
 *       ResultsTab-owned local state (useState in the body), pushed down from App (App.jsx decomp slice 2).
 *
 * --- State values ---
 * status                 - { results, is_running, log, complete }
 * config                 - full config object (assignments_folder, output_folder, roster_file, etc.)
 * rubric                 - rubric object
 * globalAINotes          - string
 * theme                  - "dark" | "light"
 * resultsPeriodFilter    - string
 * editedResults          - array
 * emailApprovals         - object { index: 'approved' | 'rejected' | 'pending' }
 * sentEmails             - object { index: true }
 * editedEmails           - object { index: { subject, body } }
 * emailStatus            - { sending, sent, failed, message }
 * autoApproveEmails      - boolean
 * gradesApproved         - boolean
 * savedAssignments       - array of assignment name strings
 * savedAssignmentData    - object { name: { aliases, title } }
 * studentAccommodations  - object { studentId: { presets, ... } }
 * sortedPeriods          - array of { filename, period_name }
 * portalSubmissions      - array
 * assessmentResults      - array of assessment result objects from /api/assessment-results
 * vportalConfigured      - boolean
 * outlookSendStatus      - { status, sent, total, failed, message }
 * focusCommsStatus       - { status, sent, total, failed, skipped, message }
 * focusCommentsStatus    - { status, entered, total, failed, message }
 * curveModal             - { show, curveType, curveValue }
 * colWidths              - array | null
 * defaultColPercents     - array
 * pendingConfirmations   - number
 * pendingConfirmationStudents - array
 * confirmationStudentFilter   - string
 * focusExportModal       - boolean (value not used but setter is)
 * reviewModal            - { show, index }  (value not used but setter is)
 *
 * --- Setter functions ---
 * setResultsPeriodFilter
 * setStatus
 * setConfig
 * setEditedResults
 * setEmailApprovals
 * setSentEmails
 * setEditedEmails
 * setEmailStatus
 * setAutoApproveEmails
 * setGradesApproved
 * setOutlookSendStatus
 * setOutlookSendPolling
 * setFocusCommsStatus
 * setFocusCommsPolling
 * setFocusCommentsStatus
 * setFocusCommentsPolling
 * setCurveModal
 * setFocusExportModal
 * setColWidths
 * setConfirmationStudentFilter
 *
 * --- Callbacks / functions ---
 * addToast               - function(message, type, duration?)
 * openReview             - function(index)
 * sendSingleEmail        - function(result, index)
 * getDefaultEmailBody    - function(index)
 * updateApprovalsBulk    - function(approvals)
 * initColWidths          - function()
 * handleResizeStart      - function(e, colIndex)
 *
 * --- Refs ---
 * tableRef               - React ref for table container
 * pendingConfirmationIds      - React ref
 * pendingConfirmationFilenames - React ref
 */

export default React.memo(function ResultsTab({
  // State
  status,
  config,
  rubric,
  globalAINotes,
  theme,
  resultsPeriodFilter,
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
  assessmentResults,
  setAssessmentResults,
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
  // Setters
  setResultsPeriodFilter,
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
  // Callbacks
  addToast,
  openReview,
  sendSingleEmail,
  getDefaultEmailBody,
  updateApprovalsBulk,
  initColWidths,
  handleResizeStart,
  // Refs
  tableRef,
  pendingConfirmationIds,
  pendingConfirmationFilenames,
}) {
  const [batchExportLoading, setBatchExportLoading] = useState(false);
  const [outlookExportLoading, setOutlookExportLoading] = useState(false);
  const [ccParents, setCcParents] = useState(false);
  const [resultsFilter, setResultsFilter] = useState("all");
  const [resultsAssignmentFilter, setResultsAssignmentFilter] = useState("");
  const [resultsSort, setResultsSort] = useState({ field: "time", direction: "desc" });
  const [resultsSearch, setResultsSearch] = useState("");
  var _assignmentSectionOpen = useState(true);
  var assignmentSectionOpen = _assignmentSectionOpen[0];
  var setAssignmentSectionOpen = _assignmentSectionOpen[1];

  return (
                <div
                  className="fade-in"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr",
                    gap: "20px",
                  }}
                >
                  {/* Assessment Results Section */}
                  <AssessmentResultsSection
                    assessmentResults={assessmentResults}
                    setAssessmentResults={setAssessmentResults}
                    config={config}
                    addToast={addToast}
                  />

                  {/* Assignment Results Section */}
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

                    {status.results.length === 0 && portalSubmissions.length === 0 ? (
                      <p
                        style={{
                          color: "var(--text-secondary)",
                          textAlign: "center",
                          padding: "40px",
                        }}
                      >
                        No results yet. Grade some assignments first.
                      </p>
                    ) : (
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
                    )}
                  </div>
                    )}
                  </div>
                </div>
  );
});
