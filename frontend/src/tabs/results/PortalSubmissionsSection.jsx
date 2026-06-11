import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

export default function PortalSubmissionsSection({
  portalSubmissions,
  resultsFilter,
  pendingConfirmations,
  vportalConfigured,
  outlookSendStatus,
  setOutlookSendStatus,
  setOutlookSendPolling,
  addToast,
  pendingConfirmationIds,
}) {
  if (portalSubmissions.length === 0 || (resultsFilter !== "all" && resultsFilter !== "portal_pending")) {
    return null;
  }
  return (
                      <div style={{
                        background: "var(--glass-bg)", borderRadius: "12px",
                        border: "1px solid rgba(234,179,8,0.15)", padding: "16px", marginBottom: "20px",
                      }}>
                        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "12px", color: "#fbbf24", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Inbox" size={18} /> Portal Submissions
                          <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "var(--text-muted)" }}>
                            ({portalSubmissions.filter(s => s.status === "submitted").length} pending)
                          </span>
                          {pendingConfirmations > 0 && vportalConfigured && (
                            <button
                              onClick={async () => {
                                if (!window.confirm("Send " + pendingConfirmations + " confirmation email(s) via Outlook?")) return;
                                try {
                                  var result = await api.sendSubmissionConfirmations();
                                  if (result.error) { addToast(result.error, "error"); return; }
                                  pendingConfirmationIds.current = result.confirmation_ids || [];
                                  setOutlookSendPolling(true);
                                  setOutlookSendStatus({ status: "running", sent: 0, total: result.total, failed: 0, message: "Starting confirmations..." });
                                  addToast("Sending " + result.total + " confirmation(s) via Outlook...", "info");
                                } catch (err) {
                                  addToast("Failed to start confirmations: " + err.message, "error");
                                }
                              }}
                              disabled={outlookSendStatus.status === "running"}
                              style={{
                                marginLeft: "auto", padding: "4px 12px", borderRadius: "6px", border: "1px solid rgba(59,130,246,0.3)",
                                background: "rgba(59,130,246,0.1)", color: "#60a5fa", fontSize: "0.8rem", fontWeight: 600,
                                cursor: outlookSendStatus.status === "running" ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: "4px",
                              }}
                              title="Send confirmation emails to students via Outlook"
                            >
                              <Icon name="Mail" size={14} /> Send Confirmations ({pendingConfirmations})
                            </button>
                          )}
                        </h3>
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                          {portalSubmissions
                            .filter(s => resultsFilter === "all" || s.status === "submitted")
                            .map((sub) => (
                            <div key={sub.submission_id} style={{
                              display: "flex", justifyContent: "space-between", alignItems: "center",
                              padding: "10px 14px", borderRadius: "8px",
                              background: sub.status === "graded" ? "rgba(34,197,94,0.08)" : "rgba(234,179,8,0.08)",
                              border: "1px solid " + (sub.status === "graded" ? "rgba(34,197,94,0.2)" : "rgba(234,179,8,0.2)"),
                            }}>
                              <div>
                                <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{sub.student_name}</span>
                                <span style={{ color: "var(--text-muted)", marginLeft: "8px", fontSize: "0.85rem" }}>
                                  {sub.assignment}{sub.period ? " \u2022 " + sub.period : ""}
                                </span>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                {sub.status === "graded" ? (
                                  <span style={{ color: "#4ade80", fontWeight: 600 }}>
                                    {sub.percentage != null ? Math.round(sub.percentage) + "%" : sub.score}
                                    {sub.letter_grade ? " (" + sub.letter_grade + ")" : ""}
                                  </span>
                                ) : (
                                  <span style={{
                                    padding: "3px 10px", borderRadius: "12px", fontSize: "0.75rem",
                                    fontWeight: 600, background: "rgba(234,179,8,0.2)", color: "#fbbf24",
                                  }}>
                                    Pending
                                  </span>
                                )}
                                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                  {new Date(sub.submitted_at).toLocaleString()}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
  );
}
