import React from "react";
import Icon from "../../components/Icon";
import ResultsFilterControls from "./ResultsFilterControls";
import ResultsExportControls from "./ResultsExportControls";

export default function ResultsHeader({
  status,
  resultsFilter,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  emailApprovals,
  resultsSort,
  setResultsSort,
  setResultsFilter,
  portalSubmissions,
  sortedPeriods,
  setResultsPeriodFilter,
  savedAssignments,
  savedAssignmentData,
  setResultsAssignmentFilter,
  curveModal,
  setCurveModal,
  resultsSearch,
  setStatus,
  setEditedResults,
  setEmailApprovals,
  setEditedEmails,
  addToast,
  gradesApproved,
  setGradesApproved,
  batchExportLoading,
  setBatchExportLoading,
  editedResults,
  setFocusExportModal,
  config,
  focusCommentsStatus,
  setFocusCommentsStatus,
  setFocusCommentsPolling,
  vportalConfigured,
  outlookExportLoading,
  setOutlookExportLoading,
  outlookSendStatus,
  setOutlookSendStatus,
  setOutlookSendPolling,
  focusCommsStatus,
  setFocusCommsStatus,
  setFocusCommsPolling,
  setConfirmationStudentFilter,
  confirmationStudentFilter,
  pendingConfirmationStudents,
  pendingConfirmations,
  pendingConfirmationFilenames,
  ccParents,
  setCcParents,
}) {
  return (
                    <div style={{ marginBottom: "20px" }}>
                      <h2
                        style={{
                          fontSize: "1.3rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          marginBottom: "15px",
                        }}
                      >
                        <Icon name="FileText" size={24} />
                        Grading Results (
                        {resultsFilter === "all" && !resultsPeriodFilter && !resultsAssignmentFilter
                          ? status.results.length
                          : status.results.filter((r, idx) => {
                              if (resultsFilter === "handwritten" && !r.is_handwritten)
                                return false;
                              if (resultsFilter === "typed" && r.is_handwritten)
                                return false;
                              if (resultsFilter === "verified" && r.marker_status !== "verified")
                                return false;
                              if (resultsFilter === "unverified" && r.marker_status !== "verified")
                                return false;
                              if (resultsFilter === "resubmission" && !r.is_resubmission)
                                return false;
                              if (resultsFilter === "approved" && emailApprovals[idx] !== "approved")
                                return false;
                              if (resultsFilter === "unapproved" && emailApprovals[idx] === "approved")
                                return false;
                              if (resultsPeriodFilter && r.period !== resultsPeriodFilter)
                                return false;
                              if (resultsAssignmentFilter && (r.assignment || r.filename) !== resultsAssignmentFilter)
                                return false;
                              return true;
                            }).length}
                        {(resultsFilter !== "all" || resultsPeriodFilter || resultsAssignmentFilter) &&
                          ` of ${status.results.length}`}
                        )
                      </h2>
                      {/* Assignment Stats - shows when assignment filter is active */}
                      {resultsAssignmentFilter && (
                        <AssignmentStats
                          status={status}
                          resultsAssignmentFilter={resultsAssignmentFilter}
                        />
                      )}
                      {status.results.length > 0 && (
                        <div
                          data-tutorial="results-filters"
                          style={{
                            display: "flex",
                            gap: "10px",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <ResultsFilterControls
                            resultsSort={resultsSort}
                            setResultsSort={setResultsSort}
                            resultsFilter={resultsFilter}
                            setResultsFilter={setResultsFilter}
                            portalSubmissions={portalSubmissions}
                            sortedPeriods={sortedPeriods}
                            resultsPeriodFilter={resultsPeriodFilter}
                            setResultsPeriodFilter={setResultsPeriodFilter}
                            savedAssignments={savedAssignments}
                            savedAssignmentData={savedAssignmentData}
                            resultsAssignmentFilter={resultsAssignmentFilter}
                            setResultsAssignmentFilter={setResultsAssignmentFilter}
                            curveModal={curveModal}
                            setCurveModal={setCurveModal}
                            resultsSearch={resultsSearch}
                            status={status}
                            setStatus={setStatus}
                            setEditedResults={setEditedResults}
                            emailApprovals={emailApprovals}
                            setEmailApprovals={setEmailApprovals}
                            setEditedEmails={setEditedEmails}
                            addToast={addToast}
                            gradesApproved={gradesApproved}
                            setGradesApproved={setGradesApproved}
                          />
                          <ResultsExportControls
                            gradesApproved={gradesApproved}
                            batchExportLoading={batchExportLoading}
                            setBatchExportLoading={setBatchExportLoading}
                            editedResults={editedResults}
                            status={status}
                            resultsAssignmentFilter={resultsAssignmentFilter}
                            resultsPeriodFilter={resultsPeriodFilter}
                            setResultsPeriodFilter={setResultsPeriodFilter}
                            setFocusExportModal={setFocusExportModal}
                            addToast={addToast}
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
                            sortedPeriods={sortedPeriods}
                            setConfirmationStudentFilter={setConfirmationStudentFilter}
                            confirmationStudentFilter={confirmationStudentFilter}
                            pendingConfirmationStudents={pendingConfirmationStudents}
                            pendingConfirmations={pendingConfirmations}
                            pendingConfirmationFilenames={pendingConfirmationFilenames}
                            ccParents={ccParents}
                            setCcParents={setCcParents}
                          />
                        </div>
                      )}
                    </div>
  );
}

function AssignmentStats({ status, resultsAssignmentFilter }) {
                        const assignmentResults = status.results.filter(r => (r.assignment || r.filename) === resultsAssignmentFilter);
                        const gradedCount = assignmentResults.length;
                        const avgScore = gradedCount > 0 ? Math.round(assignmentResults.reduce((sum, r) => sum + (parseInt(r.score) || 0), 0) / gradedCount) : 0;
                        const gradeDistribution = { A: 0, B: 0, C: 0, D: 0, F: 0 };
                        assignmentResults.forEach(r => {
                          const grade = (r.letter_grade || "F")[0];
                          if (gradeDistribution[grade] !== undefined) gradeDistribution[grade]++;
                        });
                        const periodBreakdown = {};
                        assignmentResults.forEach(r => {
                          const period = r.period || "Unknown";
                          periodBreakdown[period] = (periodBreakdown[period] || 0) + 1;
                        });
                        return (
                          <div style={{
                            background: "rgba(99,102,241,0.1)",
                            border: "1px solid rgba(99,102,241,0.2)",
                            borderRadius: "10px",
                            padding: "12px 16px",
                            marginBottom: "15px",
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "20px",
                            alignItems: "center",
                            fontSize: "0.85rem"
                          }}>
                            <div>
                              <span style={{ color: "var(--text-muted)" }}>Graded:</span>{" "}
                              <strong>{gradedCount}</strong> students
                            </div>
                            <div>
                              <span style={{ color: "var(--text-muted)" }}>Avg Score:</span>{" "}
                              <strong style={{ color: avgScore >= 80 ? "#4ade80" : avgScore >= 70 ? "#fbbf24" : "#f87171" }}>{avgScore}%</strong>
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <span style={{ color: "var(--text-muted)" }}>Grades:</span>
                              {Object.entries(gradeDistribution).map(([grade, count]) => count > 0 && (
                                <span key={grade} style={{
                                  padding: "2px 8px",
                                  borderRadius: "4px",
                                  background: grade === "A" ? "rgba(74,222,128,0.2)" : grade === "B" ? "rgba(96,165,250,0.2)" : grade === "C" ? "rgba(251,191,36,0.2)" : "rgba(248,113,113,0.2)",
                                  color: grade === "A" ? "#4ade80" : grade === "B" ? "#60a5fa" : grade === "C" ? "#fbbf24" : "#f87171",
                                  fontWeight: 600
                                }}>
                                  {grade}: {count}
                                </span>
                              ))}
                            </div>
                            {Object.keys(periodBreakdown).length > 1 && (
                              <div style={{ display: "flex", gap: "8px" }}>
                                <span style={{ color: "var(--text-muted)" }}>By Period:</span>
                                {Object.entries(periodBreakdown).sort((a, b) => a[0].localeCompare(b[0])).map(([period, count]) => (
                                  <span key={period} style={{ padding: "2px 8px", borderRadius: "4px", background: "rgba(255,255,255,0.1)" }}>
                                    {period}: {count}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
}
