import React from "react";
import Icon from "../../components/Icon";
import ResultsTableRow from "./ResultsTableRow";

export function ResultsSearchInput({ resultsSearch, setResultsSearch }) {
  return (
                        <div style={{ marginBottom: "15px" }}>
                          <div style={{ position: "relative" }}>
                            <Icon
                              name="Search"
                              size={18}
                              style={{
                                position: "absolute",
                                left: "12px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                color: "var(--text-muted)",
                              }}
                            />
                            <input
                              type="text"
                              placeholder="Search by student or assignment name..."
                              value={resultsSearch}
                              onChange={(e) => setResultsSearch(e.target.value)}
                              style={{
                                width: "100%",
                                padding: "10px 12px 10px 40px",
                                borderRadius: "8px",
                                border: "1px solid var(--glass-border)",
                                background: "var(--input-bg)",
                                color: "var(--text-primary)",
                                fontSize: "0.9rem",
                              }}
                            />
                            {resultsSearch && (
                              <button
                                onClick={() => setResultsSearch("")}
                                style={{
                                  position: "absolute",
                                  right: "12px",
                                  top: "50%",
                                  transform: "translateY(-50%)",
                                  background: "none",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  padding: "4px",
                                }}
                              >
                                <Icon name="X" size={16} />
                              </button>
                            )}
                          </div>
                        </div>
  );
}

export default function ResultsTable({
  editedResults,
  status,
  setStatus,
  setEditedResults,
  resultsFilter,
  emailApprovals,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  resultsSearch,
  resultsSort,
  colWidths,
  defaultColPercents,
  tableRef,
  initColWidths,
  handleResizeStart,
  theme,
  studentAccommodations,
  config,
  setConfig,
  addToast,
  autoApproveEmails,
  sentEmails,
  outlookSendStatus,
  openReview,
  sendSingleEmail,
}) {
  return (
                        <div style={{ overflowX: "auto" }} ref={(el) => { tableRef.current = el; if (el && !colWidths) initColWidths(); }}>
                        <table style={{ width: colWidths ? colWidths.reduce((a, b) => a + b, 0) + "px" : "100%", tableLayout: "fixed" }}>
                          {colWidths && (
                            <colgroup>
                              {colWidths.map((w, i) => (
                                <col key={i} style={{ width: w + "px" }} />
                              ))}
                            </colgroup>
                          )}
                          {!colWidths && (
                            <colgroup>
                              {defaultColPercents.map((p, i) => (
                                <col key={i} style={{ width: p + "%" }} />
                              ))}
                            </colgroup>
                          )}
                          <thead>
                            <tr>
                              {["Student", "Assignment", "Time", "Score", "Grade", "Cost", "Authenticity", "Email", "Actions"].map((label, i) => (
                                <th key={label} style={{ textAlign: i >= 3 ? "center" : undefined, position: "relative", overflow: "visible" }}>
                                  {label}
                                  {i < 8 && (
                                    <span
                                      onMouseDown={(e) => handleResizeStart(e, i)}
                                      style={{
                                        position: "absolute",
                                        right: -2,
                                        top: 4,
                                        bottom: 4,
                                        width: "4px",
                                        cursor: "col-resize",
                                        borderRadius: "2px",
                                        background: theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                                        transition: "background 0.15s",
                                        zIndex: 1,
                                      }}
                                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-primary)"; }}
                                      onMouseLeave={(e) => { e.currentTarget.style.background = theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"; }}
                                    />
                                  )}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(editedResults.length > 0
                              ? editedResults
                              : status.results
                            )
                              .filter((r) => {
                                // Apply handwritten/typed filter
                                if (
                                  resultsFilter === "handwritten" &&
                                  !r.is_handwritten
                                )
                                  return false;
                                if (
                                  resultsFilter === "typed" &&
                                  r.is_handwritten
                                )
                                  return false;
                                // Apply verified/unverified filter
                                if (
                                  resultsFilter === "verified" &&
                                  r.marker_status !== "verified"
                                )
                                  return false;
                                if (
                                  resultsFilter === "unverified" &&
                                  r.marker_status !== "unverified"
                                )
                                  return false;
                                if (
                                  resultsFilter === "mismatched" &&
                                  !r.config_mismatch
                                )
                                  return false;
                                if (
                                  resultsFilter === "resubmission" &&
                                  !r.is_resubmission
                                )
                                  return false;
                                // Apply approval filter
                                if (resultsFilter === "approved" || resultsFilter === "unapproved") {
                                  const idx = status.results.findIndex((orig) => orig.filename === r.filename);
                                  const isApproved = emailApprovals[idx] === "approved";
                                  if (resultsFilter === "approved" && !isApproved) return false;
                                  if (resultsFilter === "unapproved" && isApproved) return false;
                                }
                                // Apply period filter
                                if (resultsPeriodFilter && r.period !== resultsPeriodFilter)
                                  return false;
                                // Apply assignment filter
                                if (resultsAssignmentFilter && (r.assignment || r.filename) !== resultsAssignmentFilter)
                                  return false;
                                // Apply search filter
                                if (!resultsSearch.trim()) return true;
                                const search = resultsSearch.toLowerCase().replace(/['\u2019]/g, "");
                                return (
                                  (r.student_name || "")
                                    .toLowerCase()
                                    .replace(/['\u2019]/g, "")
                                    .includes(search) ||
                                  (r.assignment || "")
                                    .toLowerCase()
                                    .includes(search)
                                );
                              })
                              .sort((a, b) => {
                                const { field, direction } = resultsSort;
                                let cmp = 0;
                                switch (field) {
                                  case "time":
                                    const timeA = a.graded_at || "";
                                    const timeB = b.graded_at || "";
                                    cmp = timeA.localeCompare(timeB);
                                    break;
                                  case "name":
                                    cmp = (a.student_name || "").localeCompare(
                                      b.student_name || "",
                                    );
                                    break;
                                  case "assignment":
                                    cmp = (a.assignment || "").localeCompare(
                                      b.assignment || "",
                                    );
                                    break;
                                  case "score":
                                    cmp = (a.score || 0) - (b.score || 0);
                                    break;
                                  case "grade":
                                    const gradeOrder = {
                                      A: 1,
                                      B: 2,
                                      C: 3,
                                      D: 4,
                                      F: 5,
                                      ERROR: 6,
                                    };
                                    cmp =
                                      (gradeOrder[a.letter_grade] || 99) -
                                      (gradeOrder[b.letter_grade] || 99);
                                    break;
                                  default:
                                    cmp = 0;
                                }
                                return direction === "desc" ? -cmp : cmp;
                              })
                              .map((r, i) => {
                                // Find the original index for actions that need it
                                const originalIndex = status.results.findIndex(
                                  (orig) => orig.filename === r.filename,
                                );
                                return (
                                  <ResultsTableRow
                                    key={r.filename || i}
                                    r={r}
                                    originalIndex={originalIndex}
                                    status={status}
                                    setStatus={setStatus}
                                    setEditedResults={setEditedResults}
                                    studentAccommodations={studentAccommodations}
                                    config={config}
                                    setConfig={setConfig}
                                    addToast={addToast}
                                    autoApproveEmails={autoApproveEmails}
                                    sentEmails={sentEmails}
                                    emailApprovals={emailApprovals}
                                    outlookSendStatus={outlookSendStatus}
                                    openReview={openReview}
                                    sendSingleEmail={sendSingleEmail}
                                  />
                                );
                              })}
                          </tbody>
                        </table>
                        </div>
  );
}
