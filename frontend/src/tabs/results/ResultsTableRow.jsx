import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import AuthenticityCell from "./AuthenticityCell";
import StudentNameCell from "./StudentNameCell";

export default function ResultsTableRow({
  r,
  originalIndex,
  status,
  setStatus,
  setEditedResults,
  studentAccommodations,
  config,
  setConfig,
  addToast,
  autoApproveEmails,
  sentEmails,
  emailApprovals,
  outlookSendStatus,
  openReview,
  sendSingleEmail,
}) {
  return (
                                  <tr
                                    style={{
                                      background: r.edited
                                        ? "rgba(251,191,36,0.1)"
                                        : "transparent",
                                    }}
                                  >
                                    <StudentNameCell r={r} studentAccommodations={studentAccommodations} />
                                    <td
                                      style={{
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        cursor: "help",
                                      }}
                                      title={r.assignment || r.filename}
                                    >
                                      {r.assignment || r.filename}
                                    </td>
                                    <td
                                      style={{
                                        fontSize: "0.8rem",
                                        color: "var(--text-secondary)",
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {r.graded_at ? r.graded_at.replace(/^20(\d{2})/, "$1") : "-"}
                                    </td>
                                    <td style={{ textAlign: "center" }} title={r.late_penalty ? "Original: " + r.original_score + " | -" + r.late_penalty.penalty_applied + " pts (" + r.late_penalty.days_late + " day" + (r.late_penalty.days_late !== 1 ? "s" : "") + " late)" : undefined}>
                                      {r.late_penalty ? (
                                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                                          <span style={{ textDecoration: "line-through", color: "var(--text-muted)", fontSize: "0.75rem" }}>{r.original_score}</span>
                                          <span>{r.score}</span>
                                          <Icon name="Clock" size={12} style={{ color: "#f59e0b" }} />
                                        </span>
                                      ) : r.score}
                                    </td>
                                    <td style={{ textAlign: "center" }}>
                                      <span
                                        style={{
                                          display: "inline-block",
                                          padding: "4px 10px",
                                          borderRadius: "20px",
                                          fontWeight: 700,
                                          fontSize: r.letter_grade && r.letter_grade.length > 2 ? "0.7rem" : undefined,
                                          whiteSpace: "nowrap",
                                          maxWidth: "100%",
                                          overflow: "hidden",
                                          textOverflow: "ellipsis",
                                          background:
                                            r.score >= 90
                                              ? "rgba(74,222,128,0.2)"
                                              : r.score >= 80
                                                ? "rgba(96,165,250,0.2)"
                                                : r.score >= 70
                                                  ? "rgba(251,191,36,0.2)"
                                                  : "rgba(248,113,113,0.2)",
                                          color:
                                            r.score >= 90
                                              ? "#4ade80"
                                              : r.score >= 80
                                                ? "#60a5fa"
                                                : r.score >= 70
                                                  ? "#fbbf24"
                                                  : "#f87171",
                                        }}
                                        title={r.letter_grade}
                                      >
                                        {r.letter_grade}
                                      </span>
                                    </td>
                                    <td style={{ textAlign: "center", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                                      {r.token_usage?.total_cost_display || "\u2014"}
                                    </td>
                                    <AuthenticityCell
                                      r={r}
                                      config={config}
                                      setConfig={setConfig}
                                      addToast={addToast}
                                    />
                                    <EmailStatusCell
                                      r={r}
                                      originalIndex={originalIndex}
                                      autoApproveEmails={autoApproveEmails}
                                      sentEmails={sentEmails}
                                      emailApprovals={emailApprovals}
                                    />
                                    <ActionsCell
                                      r={r}
                                      originalIndex={originalIndex}
                                      status={status}
                                      setStatus={setStatus}
                                      setEditedResults={setEditedResults}
                                      openReview={openReview}
                                      sendSingleEmail={sendSingleEmail}
                                      outlookSendStatus={outlookSendStatus}
                                      addToast={addToast}
                                    />
                                  </tr>
  );
}

function EmailStatusCell({ r, originalIndex, autoApproveEmails, sentEmails, emailApprovals }) {
  return (
                                    <td style={{ textAlign: "center" }}>
                                      <div
                                        style={{
                                          display: "flex",
                                          flexDirection: "column",
                                          gap: "4px",
                                          alignItems: "center",
                                        }}
                                      >
                                        {autoApproveEmails ? (
                                          <span
                                            style={{
                                              color: "#4ade80",
                                              fontSize: "0.85rem",
                                            }}
                                          >
                                            Auto
                                          </span>
                                        ) : (
                                          <span
                                            style={{
                                              padding: "3px 8px",
                                              borderRadius: "4px",
                                              fontSize: "0.8rem",
                                              fontWeight: 600,
                                              background:
                                                sentEmails[originalIndex]
                                                  ? "rgba(59,130,246,0.25)"
                                                  : emailApprovals[
                                                      originalIndex
                                                    ] === "approved"
                                                    ? "rgba(74,222,128,0.2)"
                                                    : emailApprovals[
                                                          originalIndex
                                                        ] === "rejected"
                                                      ? "rgba(248,113,113,0.2)"
                                                      : "var(--glass-border)",
                                              color:
                                                sentEmails[originalIndex]
                                                  ? "#3b82f6"
                                                  : emailApprovals[
                                                      originalIndex
                                                    ] === "approved"
                                                    ? "#4ade80"
                                                    : emailApprovals[
                                                          originalIndex
                                                        ] === "rejected"
                                                      ? "#f87171"
                                                      : "var(--text-secondary)",
                                            }}
                                          >
                                            {sentEmails[originalIndex]
                                              ? "Sent"
                                              : emailApprovals[originalIndex] ===
                                                "approved"
                                                ? "Approved"
                                                : emailApprovals[
                                                      originalIndex
                                                    ] === "rejected"
                                                  ? "Rejected"
                                                  : "Pending"}
                                          </span>
                                        )}
                                        {r.edited && (
                                          <span
                                            style={{
                                              padding: "2px 6px",
                                              borderRadius: "4px",
                                              fontSize: "0.7rem",
                                              fontWeight: 500,
                                              background:
                                                "rgba(251,191,36,0.15)",
                                              color: "#fbbf24",
                                            }}
                                          >
                                            Edited
                                          </span>
                                        )}
                                      </div>
                                    </td>
  );
}

function ActionsCell({
  r,
  originalIndex,
  status,
  setStatus,
  setEditedResults,
  openReview,
  sendSingleEmail,
  outlookSendStatus,
  addToast,
}) {
  return (
                                    <td style={{ textAlign: "center" }}>
                                      <div style={{ display: "flex", gap: "4px", alignItems: "center", justifyContent: "center" }}>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          openReview(originalIndex);
                                        }}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "#a5b4fc",
                                          cursor: "pointer",
                                          padding: "4px",
                                        }}
                                        title="Edit"
                                      >
                                        <Icon name="Edit" size={16} />
                                      </button>
                                      <button
                                        onClick={() => addToast("Regrading is not available in portal mode. Students can resubmit via the portal.", "info")}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "#fbbf24",
                                          cursor: "pointer",
                                          padding: "4px",
                                        }}
                                        title="Regrade this assignment"
                                        disabled={status.is_running}
                                      >
                                        <Icon name="RefreshCw" size={16} />
                                      </button>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          sendSingleEmail(r, originalIndex);
                                        }}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: r.student_email ? "#4ade80" : "#6b7280",
                                          cursor: r.student_email && outlookSendStatus.status !== "running" ? "pointer" : "not-allowed",
                                          padding: "4px",
                                          opacity: r.student_email && outlookSendStatus.status !== "running" ? 1 : 0.5,
                                        }}
                                        title={r.student_email ? `Send via Outlook to ${r.student_email}` : "No email address"}
                                        disabled={!r.student_email || outlookSendStatus.status === "running"}
                                      >
                                        <Icon name="Mail" size={16} />
                                      </button>
                                      <button
                                        onClick={async (e) => {
                                          e.stopPropagation();
                                          if (
                                            confirm(
                                              `Delete result for "${r.student_name}"?`,
                                            )
                                          ) {
                                            try {
                                              await api.deleteResult(
                                                r.filename,
                                              );
                                              setStatus((prev) => ({
                                                ...prev,
                                                results: prev.results.filter(
                                                  (result) =>
                                                    result.filename !==
                                                    r.filename,
                                                ),
                                              }));
                                              setEditedResults((prev) =>
                                                prev.filter(
                                                  (result) =>
                                                    result.filename !==
                                                    r.filename,
                                                ),
                                              );
                                              // Email approvals are re-indexed automatically by the
                                              // useEffect in App.jsx that watches status.results changes.
                                            } catch (err) {
                                              addToast(
                                                "Error deleting result: " +
                                                  err.message,
                                                "error",
                                              );
                                            }
                                          }
                                        }}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "#f87171",
                                          cursor: "pointer",
                                          padding: "4px",
                                        }}
                                        title="Delete"
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                      </div>
                                    </td>
  );
}
