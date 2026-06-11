import React from "react";
import Icon from "../Icon";

export default function EmailApprovalActions(props) {
  const { addToast, autoApproveEmails, emailApprovals, reviewModal, sentEmails, setSentEmails, updateApprovalStatus } = props;
  if (autoApproveEmails) return null;
  return (
                          <div
                            style={{
                              marginTop: "20px",
                              display: "flex",
                              gap: "10px",
                              justifyContent: "center",
                            }}
                          >
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                addToast(
                                  "Email approved for sending",
                                  "success",
                                );
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "linear-gradient(135deg, #22c55e, #16a34a)"
                                    : "rgba(74,222,128,0.15)",
                                border:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "none"
                                    : "1px solid rgba(74,222,128,0.3)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "#fff"
                                    : "#4ade80",
                              }}
                            >
                              <Icon name="Check" size={18} />
                              {emailApprovals[reviewModal.index] === "approved"
                                ? "Approved"
                                : "Approve Email"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "rejected");
                                addToast("Email marked as rejected", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "rgba(248,113,113,0.2)"
                                    : "var(--glass-bg)",
                                border: "1px solid var(--glass-border)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "#f87171"
                                    : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="X" size={18} />
                              {emailApprovals[reviewModal.index] === "rejected"
                                ? "Rejected"
                                : "Reject"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                setSentEmails((prev) => ({
                                  ...prev,
                                  [reviewModal.index]: true,
                                }));
                                addToast("Marked as sent (no email sent)", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background: sentEmails[reviewModal.index]
                                  ? "rgba(59,130,246,0.25)"
                                  : "var(--glass-bg)",
                                border: sentEmails[reviewModal.index]
                                  ? "1px solid rgba(59,130,246,0.4)"
                                  : "1px solid var(--glass-border)",
                                color: sentEmails[reviewModal.index]
                                  ? "#3b82f6"
                                  : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="Send" size={18} />
                              {sentEmails[reviewModal.index]
                                ? "Sent"
                                : "Mark as Sent"}
                            </button>
                          </div>
  );
}
