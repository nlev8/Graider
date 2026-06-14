import React, { useState } from "react";
import AssessmentResultsSection from "./results/AssessmentResultsSection";
import AssignmentResultsSection from "./results/AssignmentResultsSection";

/*
 * Props required by ResultsTab:
 *
 * NOTE: The tab's sections are composed from ./results/* (CQ wave-1 split,
 *       behavior-preserving): AssessmentResultsSection, AssignmentResultsSection
 *       (filter/export controls, header, table, send button — extracted in CQ
 *       wave-3 split), and the remaining results/* sub-components.
 *
 * NOTE: resultsFilter / resultsAssignmentFilter / resultsSort / resultsSearch /
 *       batchExportLoading / outlookExportLoading / ccParents / assignmentSectionOpen
 *       (and their setters) are ResultsTab-owned local state (useState in the body),
 *       pushed down as props to AssignmentResultsSection.
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
                  <AssignmentResultsSection
                    assignmentSectionOpen={assignmentSectionOpen}
                    setAssignmentSectionOpen={setAssignmentSectionOpen}
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
                    status={status}
                    config={config}
                    theme={theme}
                    resultsPeriodFilter={resultsPeriodFilter}
                    setResultsPeriodFilter={setResultsPeriodFilter}
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
                </div>
  );
});
