import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

export default function SendApprovedEmailsButton({
  emailApprovals,
  autoApproveEmails,
  status,
  editedEmails,
  getDefaultEmailBody,
  emailStatus,
  setEmailStatus,
  sentEmails,
  setSentEmails,
  config,
}) {
  if (
    Object.values(emailApprovals).filter((v) => v === "approved").length === 0 ||
    autoApproveEmails
  ) {
    return null;
  }
  return (
                            <div
                              style={{
                                marginTop: "20px",
                                display: "flex",
                                justifyContent: "flex-end",
                              }}
                            >
                              <button
                                onClick={async () => {
                                  // Build approved results with custom email content
                                  const approvedResults = status.results
                                    .map((r, i) => {
                                      if (emailApprovals[i] !== "approved")
                                        return null;
                                      const edited = editedEmails[i];
                                      const emailToUse = edited?.email || r.student_email;
                                      if (!emailToUse) return null; // Skip if no email
                                      return {
                                        ...r,
                                        student_email: emailToUse,
                                        custom_email_subject:
                                          edited?.subject ||
                                          `Grade Report: ${r.assignment}`,
                                        custom_email_body:
                                          edited?.body ||
                                          getDefaultEmailBody(i),
                                      };
                                    })
                                    .filter(Boolean);
                                  if (approvedResults.length === 0) return;
                                  setEmailStatus({
                                    sending: true,
                                    sent: 0,
                                    failed: 0,
                                    message: "Sending emails...",
                                  });
                                  try {
                                    const result =
                                      await api.sendEmails(approvedResults, config.teacher_email, config.teacher_name, config.email_signature);
                                    setEmailStatus({
                                      sending: false,
                                      sent:
                                        result.sent || approvedResults.length,
                                      failed: result.failed || 0,
                                      message: `Sent ${result.sent || approvedResults.length} emails successfully!`,
                                    });
                                    // Mark approved emails as sent
                                    const newSentEmails = { ...sentEmails };
                                    Object.keys(emailApprovals).forEach((idx) => {
                                      if (emailApprovals[idx] === "approved") {
                                        newSentEmails[idx] = true;
                                      }
                                    });
                                    setSentEmails(newSentEmails);
                                  } catch (e) {
                                    setEmailStatus({
                                      sending: false,
                                      sent: 0,
                                      failed: approvedResults.length,
                                      message:
                                        "Error sending emails: " + e.message,
                                    });
                                  }
                                }}
                                className="btn btn-primary"
                                disabled={emailStatus.sending}
                              >
                                <Icon name="Send" size={18} />
                                Send{" "}
                                {
                                  Object.values(emailApprovals).filter(
                                    (v) => v === "approved",
                                  ).length
                                }{" "}
                                Approved Emails
                              </button>
                            </div>
  );
}
