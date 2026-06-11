import React from "react";
import Icon from "../../components/Icon";

export default function AutoApproveControls({
  status,
  autoApproveEmails,
  setAutoApproveEmails,
  resultsFilter,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  emailApprovals,
  updateApprovalsBulk,
  sentEmails,
  setSentEmails,
  addToast,
}) {
  if (status.results.length === 0) return null;
  return (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: "15px",
                          marginBottom: "20px",
                          padding: "12px 15px",
                          background: "var(--input-bg)",
                          borderRadius: "10px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <button
                            onClick={() =>
                              setAutoApproveEmails(!autoApproveEmails)
                            }
                            style={{
                              width: "44px",
                              height: "24px",
                              borderRadius: "12px",
                              border: "none",
                              background: autoApproveEmails
                                ? "#6366f1"
                                : "var(--btn-secondary-border)",
                              cursor: "pointer",
                              position: "relative",
                              transition: "background 0.2s",
                            }}
                          >
                            <div
                              style={{
                                width: "18px",
                                height: "18px",
                                borderRadius: "50%",
                                background: "#fff",
                                position: "absolute",
                                top: "3px",
                                left: autoApproveEmails ? "23px" : "3px",
                                transition: "left 0.2s",
                              }}
                            />
                          </button>
                          <span style={{ fontWeight: 600 }}>
                            Auto-Approve Emails
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {autoApproveEmails
                            ? "Emails will be sent automatically"
                            : "Review each email before sending"}
                        </span>
                        {!autoApproveEmails && (
                          <div
                            style={{
                              marginLeft: "auto",
                              display: "flex",
                              gap: "10px",
                            }}
                          >
                            {(resultsFilter !== "all" || resultsPeriodFilter || resultsAssignmentFilter) && (
                              <button
                                onClick={() => {
                                  const approvals = { ...emailApprovals };
                                  status.results.forEach((r, i) => {
                                    // Apply same filters as the display
                                    if (resultsFilter === "handwritten" && !r.is_handwritten) return;
                                    if (resultsFilter === "typed" && r.is_handwritten) return;
                                    if (resultsFilter === "verified" && r.marker_status !== "verified") return;
                                    if (resultsFilter === "unverified" && r.marker_status !== "verified") return;
                                    if (resultsFilter === "resubmission" && !r.is_resubmission) return;
                                    if (resultsFilter === "approved" && emailApprovals[i] !== "approved") return;
                                    if (resultsFilter === "unapproved" && emailApprovals[i] === "approved") return;
                                    if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
                                    if (resultsAssignmentFilter && (r.assignment || r.filename) !== resultsAssignmentFilter) return;
                                    approvals[i] = "approved";
                                  });
                                  updateApprovalsBulk(approvals);
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(99,102,241,0.15)",
                                  border: "1px solid rgba(99,102,241,0.3)",
                                }}
                              >
                                <Icon name="Filter" size={14} />
                                Approve Filtered
                              </button>
                            )}
                            <button
                              onClick={() => {
                                const approvals = {};
                                status.results.forEach((_, i) => {
                                  approvals[i] = "approved";
                                });
                                updateApprovalsBulk(approvals);
                              }}
                              className="btn btn-secondary"
                              style={{
                                fontSize: "0.85rem",
                                padding: "6px 12px",
                              }}
                            >
                              <Icon name="CheckCircle" size={14} />
                              Approve All
                            </button>
                            {Object.keys(emailApprovals).length > 0 && (
                              <button
                                onClick={() => {
                                  updateApprovalsBulk({});
                                  addToast("All approvals cleared", "info");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(239, 68, 68, 0.15)",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  color: "#f87171",
                                }}
                              >
                                <Icon name="X" size={14} />
                                Clear Approvals
                              </button>
                            )}
                            {Object.values(emailApprovals).some((v) => v === "approved") && (
                              <button
                                onClick={() => {
                                  const newSentEmails = { ...sentEmails };
                                  Object.keys(emailApprovals).forEach((idx) => {
                                    if (emailApprovals[idx] === "approved") {
                                      newSentEmails[idx] = true;
                                    }
                                  });
                                  setSentEmails(newSentEmails);
                                  addToast("All approved emails marked as sent (no emails sent)", "info");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(59, 130, 246, 0.15)",
                                  border: "1px solid rgba(59, 130, 246, 0.3)",
                                  color: "#3b82f6",
                                }}
                              >
                                <Icon name="Send" size={14} />
                                Mark All as Sent
                              </button>
                            )}
                          </div>
                        )}
                      </div>
  );
}
