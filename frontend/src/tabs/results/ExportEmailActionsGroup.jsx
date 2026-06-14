import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/**
 * Email Actions Group — Focus SIS only (rendered when config.sis_type === 'focus').
 * Extracted from ResultsExportControls to keep that component ≤200 LOC (CQ wave-3).
 * Pure prop extraction — no behavior change.
 */
export default function ExportEmailActionsGroup({
  config,
  resultsAssignmentFilter,
  status,
  gradesApproved,
  outlookExportLoading,
  setOutlookExportLoading,
  outlookSendStatus,
  setOutlookSendStatus,
  setOutlookSendPolling,
  focusCommsStatus,
  setFocusCommsStatus,
  setFocusCommsPolling,
  vportalConfigured,
  addToast,
}) {
  return (
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
  );
}
