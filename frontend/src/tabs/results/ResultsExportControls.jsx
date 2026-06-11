import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import ExportGradesDropdown from "./ExportGradesDropdown";

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
                          {/* Email Actions Group — Focus SIS only */}
                          {config.sis_type === 'focus' && (
                          <div data-tutorial="results-email" style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "rgba(234,179,8,0.06)" }}>
                          <button
                            onClick={async () => {
                              setOutlookExportLoading(true);
                              try {
                                const assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                                const resultsToExport = resultsAssignmentFilter
                                  ? status.results.filter(function(r) { return r.assignment === resultsAssignmentFilter; })
                                  : status.results;

                                var result = await api.exportOutlookEmails({
                                  results: resultsToExport,
                                  assignment: assignment,
                                });

                                if (result.error) {
                                  addToast(result.error, "error");
                                } else {
                                  var msg = "Generated " + result.count + " parent emails";
                                  if (result.no_contact && result.no_contact.length > 0) {
                                    msg += " (" + result.no_contact.length + " missing parent email)";
                                  }
                                  addToast(msg, "success");
                                }
                              } catch (err) {
                                addToast("Outlook export error: " + err.message, "error");
                              } finally {
                                setOutlookExportLoading(false);
                              }
                            }}
                            className="btn btn-secondary"
                            disabled={!gradesApproved || outlookExportLoading || status.results.length === 0}
                            style={{ opacity: gradesApproved ? 1 : 0.5 }}
                            title={gradesApproved ? "Generate parent emails from contacts" : "Approve grades first"}
                          >
                            <Icon name="Mail" size={18} />
                            {outlookExportLoading ? "Generating..." : "Parent Emails"}
                          </button>
                          <button
                            onClick={async () => {
                              var assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                              var resultsToSend = resultsAssignmentFilter
                                ? status.results.filter(function(r) { return r.assignment === resultsAssignmentFilter; })
                                : status.results;
                              if (!confirm("Send " + resultsToSend.length + " parent messages via Focus SIS?" + String.fromCharCode(10) + String.fromCharCode(10) + "Email + SMS will be sent through your school Focus account.")) return;
                              try {
                                var exportResult = await api.exportOutlookEmails({
                                  results: resultsToSend,
                                  assignment: assignment,
                                });
                                if (exportResult.error) {
                                  addToast(exportResult.error, "error");
                                  return;
                                }
                                var focusMessages = (exportResult.emails || []).map(function(e) {
                                  return {
                                    student_name: e.student_name || "",
                                    subject: e.subject || "",
                                    email_body: e.body || "",
                                    sms_body: "",
                                    cc_emails: e.cc ? e.cc.split(",").map(function(s) { return s.trim(); }).filter(Boolean) : [],
                                  };
                                });
                                if (focusMessages.length === 0) {
                                  addToast("No messages to send", "warning");
                                  return;
                                }
                                var result = await api.sendFocusComms({ messages: focusMessages });
                                if (result.error) {
                                  addToast(result.error, "error");
                                } else {
                                  setFocusCommsPolling(true);
                                  setFocusCommsStatus({ status: "running", sent: 0, total: result.total, failed: 0, skipped: 0, message: "Starting..." });
                                  addToast("Focus sending started (" + result.total + " messages)", "info");
                                }
                              } catch (err) {
                                addToast("Focus send error: " + err.message, "error");
                              }
                            }}
                            className="btn btn-primary"
                            disabled={!gradesApproved || focusCommsStatus.status === "running" || status.results.length === 0 || !vportalConfigured}
                            style={{ opacity: gradesApproved ? 1 : 0.5 }}
                            title={!gradesApproved ? "Approve grades first" : vportalConfigured ? "Send parent emails + SMS via Focus SIS" : "Configure VPortal credentials in Settings first"}
                          >
                            <Icon name="Send" size={18} />
                            {focusCommsStatus.status === "running"
                              ? "Sending " + focusCommsStatus.sent + "/" + focusCommsStatus.total + "..."
                              : "Send via Focus"}
                          </button>
                          <button
                            onClick={async () => {
                              var assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                              var resultsToSend = resultsAssignmentFilter
                                ? status.results.filter(function(r) { return r.assignment === resultsAssignmentFilter; })
                                : status.results;
                              if (!confirm("Send " + resultsToSend.length + " parent emails via Outlook?" + String.fromCharCode(10) + String.fromCharCode(10) + "A browser window will open to send from your school account.")) return;
                              try {
                                var result = await api.sendOutlookEmails({
                                  results: resultsToSend,
                                  assignment: assignment,
                                  type: "parent",
                                  teacher_name: config.teacher_name,
                                  email_signature: config.email_signature,
                                  include_secondary: true,
                                });
                                if (result.error) {
                                  addToast(result.error, "error");
                                } else {
                                  setOutlookSendPolling(true);
                                  setOutlookSendStatus({ status: "running", sent: 0, total: result.total, failed: 0, message: "Starting..." });
                                  addToast("Outlook sending started (" + result.total + " emails)", "info");
                                }
                              } catch (err) {
                                addToast("Outlook send error: " + err.message, "error");
                              }
                            }}
                            className="btn btn-secondary"
                            disabled={!gradesApproved || outlookSendStatus.status === "running" || status.results.length === 0 || !vportalConfigured}
                            style={{ opacity: gradesApproved ? 1 : 0.5 }}
                            title={!gradesApproved ? "Approve grades first" : vportalConfigured ? "Send parent emails from your Outlook account" : "Configure VPortal credentials in Settings first"}
                          >
                            <Icon name="Send" size={18} />
                            {outlookSendStatus.status === "running"
                              ? "Sending " + outlookSendStatus.sent + "/" + outlookSendStatus.total + "..."
                              : "Send via Outlook"}
                          </button>
                          </div>
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
