import React from "react";
import Icon from "../Icon";
import EmailApprovalActions from "./EmailApprovalActions";

export default function EmailPreviewTab(props) {
  const { config, editedEmails, r, reviewModal, setEditedEmails, setStatus, status } = props;
  return (
                      <div
                        style={{ flex: 1, padding: "20px", overflow: "auto" }}
                      >
                        <div
                          style={{
                            background: "#fff",
                            borderRadius: "12px",
                            padding: "30px",
                            color: "#333",
                            fontFamily: "Georgia, serif",
                            lineHeight: 1.7,
                            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: "20px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid #eee",
                            }}
                          >
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <span>To:</span>
                              <input
                                type="email"
                                value={editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email ?? ""}
                                onChange={(e) => {
                                  const newEmail = e.target.value;
                                  const studentId = r.student_id;
                                  const studentName = r.student_name;

                                  // Update editedEmails for ALL results with the same student
                                  setEditedEmails((prev) => {
                                    const updated = { ...prev };
                                    status.results.forEach((result, idx) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        updated[idx] = {
                                          ...prev[idx],
                                          email: newEmail,
                                        };
                                      }
                                    });
                                    return updated;
                                  });

                                  // Also update status.results so it persists when saved
                                  setStatus((prev) => ({
                                    ...prev,
                                    results: prev.results.map((result) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        return { ...result, student_email: newEmail };
                                      }
                                      return result;
                                    }),
                                  }));
                                }}
                                placeholder="Enter student email..."
                                style={{
                                  flex: 1,
                                  padding: "4px 8px",
                                  border: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "1px solid #ddd" : "1px solid #f87171",
                                  borderRadius: "4px",
                                  fontSize: "0.85rem",
                                  background: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "#fff" : "#fef2f2",
                                }}
                              />
                              {!(r.student_email || r.email) && !editedEmails[reviewModal.index]?.email && (
                                <span style={{ color: "#f87171", fontSize: "0.75rem" }}>
                                  (not found)
                                </span>
                              )}
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                              }}
                            >
                              Subject: {r.assignment || "Assignment"} - Grade:{" "}
                              {r.letter_grade} ({r.score}%)
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Dear{" "}
                              {r.first_name ||
                                r.student_name?.split(" ")[0] ||
                                "Student"}
                              ,
                            </p>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Your assignment{" "}
                              <strong>{r.assignment || "Assignment"}</strong>{" "}
                              has been graded.
                            </p>
                            <div
                              style={{
                                background:
                                  r.score >= 90
                                    ? "#dcfce7"
                                    : r.score >= 80
                                      ? "#dbeafe"
                                      : r.score >= 70
                                        ? "#fef3c7"
                                        : "#fee2e2",
                                padding: "15px 20px",
                                borderRadius: "8px",
                                marginBottom: "20px",
                                textAlign: "center",
                              }}
                            >
                              <div
                                style={{
                                  fontSize: "2rem",
                                  fontWeight: 700,
                                  color:
                                    r.score >= 90
                                      ? "#16a34a"
                                      : r.score >= 80
                                        ? "#2563eb"
                                        : r.score >= 70
                                          ? "#d97706"
                                          : "#dc2626",
                                }}
                              >
                                {r.letter_grade}
                              </div>
                              <div style={{ fontSize: "1rem", color: "#666" }}>
                                {r.score} / 100
                              </div>
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <h4
                              style={{
                                margin: "0 0 10px 0",
                                fontSize: "1rem",
                                color: "#333",
                              }}
                            >
                              Feedback:
                            </h4>
                            <div
                              style={{ whiteSpace: "pre-wrap", color: "#444" }}
                            >
                              {r.feedback || "(No feedback provided)"}
                            </div>
                          </div>
                          <p
                            style={{
                              margin: "20px 0 0 0",
                              color: "#666",
                              fontSize: "0.9rem",
                            }}
                          >
                            If you have any questions about your grade, please
                            see me during class or office hours.
                          </p>
                          <div style={{ margin: "15px 0 0 0", color: "#666", whiteSpace: "pre-wrap" }}>
                            {config.email_signature ? (
                              config.email_signature
                            ) : (
                              <>
                                Best regards,
                                <br />
                                <strong>
                                  {config.teacher_name || "Your Teacher"}
                                </strong>
                                {config.school_name && (
                                  <>
                                    <br />
                                    <span>{config.school_name}</span>
                                  </>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                        {/* Approve/Reject Buttons */}
                        <EmailApprovalActions {...props} />
                        <p
                          style={{
                            marginTop: "15px",
                            fontSize: "0.8rem",
                            color: "var(--text-muted)",
                            textAlign: "center",
                          }}
                        >
                          <Icon
                            name="Info"
                            size={12}
                            style={{
                              marginRight: "4px",
                              verticalAlign: "middle",
                            }}
                          />
                          Editing feedback in "Grade & Feedback" tab updates
                          this preview automatically
                        </p>
                      </div>
  );
}
