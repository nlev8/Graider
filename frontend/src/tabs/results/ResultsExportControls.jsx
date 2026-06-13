import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import ExportGradesDropdown from "./ExportGradesDropdown";
import ExportEmailActionsGroup from "./ExportEmailActionsGroup";

export default function ResultsExportControls({
  gradesApproved,
  batchExportLoading,
  setBatchExportLoading,
  editedResults,
  status,
  resultsAssignmentFilter,
  resultsPeriodFilter,
  setResultsPeriodFilter,
  setFocusExportModal,
  addToast,
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
  sortedPeriods,
  setConfirmationStudentFilter,
  confirmationStudentFilter,
  pendingConfirmationStudents,
  pendingConfirmations,
  pendingConfirmationFilenames,
  ccParents,
  setCcParents,
}) {
  return (
    <>
                          {/* Export Grades Dropdown + Upload Comments */}
                          <div data-tutorial="results-focus" style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "rgba(99,102,241,0.06)" }}>
                          <ExportGradesDropdown
                            gradesApproved={gradesApproved}
                            batchExportLoading={batchExportLoading}
                            setBatchExportLoading={setBatchExportLoading}
                            editedResults={editedResults}
                            status={status}
                            resultsAssignmentFilter={resultsAssignmentFilter}
                            resultsPeriodFilter={resultsPeriodFilter}
                            setFocusExportModal={setFocusExportModal}
                            addToast={addToast}
                            config={config}
                          />
                          <button
                            onClick={async () => {
                              var assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                              if (!confirm("Upload comments to Focus gradebook for \"" + assignment + "\"?" + String.fromCharCode(10) + String.fromCharCode(10) + "This will open a browser window and log into Focus to enter feedback comments for each student." + String.fromCharCode(10) + String.fromCharCode(10) + "Make sure you have already run 'Batch Focus' export first.")) return;
                              try {
                                var result = await api.uploadFocusComments({
                                  use_manifest: true,
                                  assignment: assignment,
                                });
                                if (result.error) {
                                  addToast(result.error, "error");
                                } else {
                                  setFocusCommentsPolling(true);
                                  setFocusCommentsStatus({ status: "running", entered: 0, total: result.total, failed: 0, message: "Starting..." });
                                  addToast("Focus comment upload started (" + result.total + " students)", "info");
                                }
                              } catch (err) {
                                addToast("Focus upload error: " + err.message, "error");
                              }
                            }}
                            className="btn btn-secondary"
                            disabled={!gradesApproved || focusCommentsStatus.status === "running" || status.results.length === 0 || !vportalConfigured}
                            style={{ opacity: gradesApproved ? 1 : 0.5 }}
                            title={!gradesApproved ? "Approve grades first" : vportalConfigured ? "Upload feedback comments to Focus gradebook" : "Configure VPortal credentials in Settings first"}
                          >
                            <Icon name="MessageSquare" size={18} />
                            {focusCommentsStatus.status === "running"
                              ? "Uploading " + focusCommentsStatus.entered + "/" + focusCommentsStatus.total + "..."
                              : "Upload Comments"}
                          </button>
                          </div>
                          {/* Email Actions Group — Focus SIS only (extracted to ExportEmailActionsGroup) */}
                          {config.sis_type === 'focus' && (
                            <ExportEmailActionsGroup
                              config={config}
                              resultsAssignmentFilter={resultsAssignmentFilter}
                              status={status}
                              gradesApproved={gradesApproved}
                              outlookExportLoading={outlookExportLoading}
                              setOutlookExportLoading={setOutlookExportLoading}
                              outlookSendStatus={outlookSendStatus}
                              setOutlookSendStatus={setOutlookSendStatus}
                              setOutlookSendPolling={setOutlookSendPolling}
                              focusCommsStatus={focusCommsStatus}
                              setFocusCommsStatus={setFocusCommsStatus}
                              setFocusCommsPolling={setFocusCommsPolling}
                              vportalConfigured={vportalConfigured}
                              addToast={addToast}
                            />
                          )}
                          {/* Confirmation Emails Group */}
                          {config.assignments_folder && (
                            <div data-tutorial="results-confirmations" style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.2)", background: "rgba(59,130,246,0.06)" }}>
                            {sortedPeriods.length > 0 && (
                              <select
                                className="input"
                                style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                                value={resultsPeriodFilter}
                                onChange={(e) => { setResultsPeriodFilter(e.target.value); setConfirmationStudentFilter(""); }}
                              >
                                <option value="">All Periods</option>
                                {sortedPeriods.map((p) => (
                                  <option key={p.filename} value={p.period_name}>
                                    {p.period_name}
                                  </option>
                                ))}
                              </select>
                            )}
                            {pendingConfirmationStudents.length > 0 && (
                              <select
                                className="input"
                                style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                                value={confirmationStudentFilter}
                                onChange={(e) => setConfirmationStudentFilter(e.target.value)}
                              >
                                <option value="">All Students ({pendingConfirmationStudents.length})</option>
                                {pendingConfirmationStudents.map((name) => (
                                  <option key={name} value={name}>{name}</option>
                                ))}
                              </select>
                            )}
                            <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.82rem", cursor: "pointer", whiteSpace: "nowrap" }}>
                              <input type="checkbox" checked={ccParents} onChange={(e) => setCcParents(e.target.checked)} />
                              CC Parents
                            </label>
                            <button
                              onClick={async () => {
                                var filterLabel = confirmationStudentFilter || resultsPeriodFilter || "";
                                var label = pendingConfirmations + " confirmation email(s)" + (filterLabel ? " for " + filterLabel : "");
                                if (!window.confirm("Send " + label + " via Outlook?")) return;
                                try {
                                  var result = await api.sendFileConfirmations({
                                    assignments_folder: config.assignments_folder,
                                    teacher_name: config.teacher_name || "Your Teacher",
                                    period_filter: resultsPeriodFilter,
                                    student_filter: confirmationStudentFilter,
                                    cc_parents: ccParents,
                                  });
                                  if (result.error) { addToast(result.error, "error"); return; }
                                  pendingConfirmationFilenames.current = result.sent_filenames || [];
                                  setOutlookSendPolling(true);
                                  setOutlookSendStatus({ status: "running", sent: 0, total: result.total, failed: 0, message: "Starting confirmations..." });
                                  addToast("Sending " + result.total + " confirmation(s) via Outlook...", "info");
                                } catch (err) {
                                  addToast("Failed to send confirmations: " + err.message, "error");
                                }
                              }}
                              className="btn btn-secondary"
                              disabled={outlookSendStatus.status === "running" || pendingConfirmations === 0}
                              title={pendingConfirmations === 0 ? "No pending confirmations" : "Send submission confirmation emails to students via Outlook"}
                            >
                              <Icon name="Mail" size={18} />
                              {"Send Confirmations (" + pendingConfirmations + ")"}
                            </button>
                            </div>
                          )}
    </>
  );
}
