import React from "react";
import Icon from "../../components/Icon";
import ResultsClearButton from "./ResultsClearButton";

export default function ResultsFilterControls({
  resultsSort,
  setResultsSort,
  resultsFilter,
  setResultsFilter,
  portalSubmissions,
  sortedPeriods,
  resultsPeriodFilter,
  setResultsPeriodFilter,
  savedAssignments,
  savedAssignmentData,
  resultsAssignmentFilter,
  setResultsAssignmentFilter,
  curveModal,
  setCurveModal,
  resultsSearch,
  status,
  setStatus,
  setEditedResults,
  emailApprovals,
  setEmailApprovals,
  setEditedEmails,
  addToast,
  gradesApproved,
  setGradesApproved,
}) {
  return (
    <>
                          {/* Sort Dropdown */}
                          <select
                            className="input"
                            value={
                              resultsSort.field + "_" + resultsSort.direction
                            }
                            onChange={(e) => {
                              const [field, direction] =
                                e.target.value.split("_");
                              setResultsSort({ field, direction });
                            }}
                            style={{
                              width: "auto",
                              padding: "8px 12px",
                              fontSize: "0.85rem",
                            }}
                          >
                            <option value="time_desc">Newest First</option>
                            <option value="time_asc">Oldest First</option>
                            <option value="name_asc">Name (A-Z)</option>
                            <option value="name_desc">Name (Z-A)</option>
                            <option value="score_desc">Score (High-Low)</option>
                            <option value="score_asc">Score (Low-High)</option>
                            <option value="assignment_asc">
                              Assignment (A-Z)
                            </option>
                            <option value="assignment_desc">
                              Assignment (Z-A)
                            </option>
                            <option value="grade_asc">Grade (A-F)</option>
                            <option value="grade_desc">Grade (F-A)</option>
                          </select>
                          {/* Filter Dropdown */}
                          <select
                            className="input"
                            value={resultsFilter}
                            onChange={(e) => setResultsFilter(e.target.value)}
                            style={{
                              width: "auto",
                              padding: "8px 12px",
                              fontSize: "0.85rem",
                            }}
                          >
                            <option value="all">All Results</option>
                            <option value="approved">Approved</option>
                            <option value="unapproved">Needs Review</option>
                            <option value="handwritten">
                              Handwritten Only
                            </option>
                            <option value="typed">Typed Only</option>
                            <option value="verified">Verified Only</option>
                            <option value="unverified">Unverified Only</option>
                            <option value="mismatched">&#x26A0;&#xFE0F; Config Mismatch</option>
                            <option value="resubmission">Resubmissions</option>
                            {portalSubmissions.length > 0 && (
                              <option value="portal_pending">
                                Portal Pending ({portalSubmissions.filter(s => s.status === "submitted").length})
                              </option>
                            )}
                          </select>
                          {/* Period Filter Dropdown */}
                          {sortedPeriods.length > 0 && (
                            <select
                              className="input"
                              value={resultsPeriodFilter}
                              onChange={(e) => setResultsPeriodFilter(e.target.value)}
                              style={{
                                width: "auto",
                                padding: "8px 12px",
                                fontSize: "0.85rem",
                              }}
                            >
                              <option value="">All Periods</option>
                              {sortedPeriods.map((p) => (
                                <option key={p.filename} value={p.period_name}>
                                  {p.period_name}
                                </option>
                              ))}
                            </select>
                          )}
                          {/* Assignment Filter Dropdown - shows saved assignments from Builder */}
                          {status.results.length > 0 && savedAssignments.length > 0 && (
                            <select
                              className="input"
                              value={resultsAssignmentFilter}
                              onChange={(e) => setResultsAssignmentFilter(e.target.value)}
                              title={resultsAssignmentFilter || "Filter by assignment"}
                              style={{
                                width: "auto",
                                padding: "8px 12px",
                                fontSize: "0.85rem",
                                maxWidth: "250px",
                              }}
                            >
                              <option value="">All Assignments</option>
                              {savedAssignments
                                .map((name) => (savedAssignmentData[name] || {}).title || name)
                                .filter((title, i, arr) => arr.indexOf(title) === i)
                                .map((title) => (
                                  <option key={title} value={title} title={title}>
                                    {title.length > 35 ? title.substring(0, 35) + "..." : title}
                                  </option>
                                ))}
                            </select>
                          )}
                          {/* Apply Curve Button - shows when period is filtered */}
                          {resultsPeriodFilter && (
                            <button
                              onClick={() => setCurveModal({ ...curveModal, show: true })}
                              className="btn btn-secondary"
                              style={{
                                background: "linear-gradient(135deg, rgba(168, 85, 247, 0.2), rgba(139, 92, 246, 0.2))",
                                borderColor: "#a855f7",
                              }}
                              title="Apply a grade curve to all filtered results"
                            >
                              <Icon name="TrendingUp" size={18} />
                              Apply Curve
                            </button>
                          )}
                          <ResultsClearButton
                            resultsFilter={resultsFilter}
                            resultsPeriodFilter={resultsPeriodFilter}
                            resultsAssignmentFilter={resultsAssignmentFilter}
                            resultsSearch={resultsSearch}
                            status={status}
                            emailApprovals={emailApprovals}
                            setStatus={setStatus}
                            setEditedResults={setEditedResults}
                            setEmailApprovals={setEmailApprovals}
                            setEditedEmails={setEditedEmails}
                            addToast={addToast}
                          />
                          {/* Approval Gate Checkbox */}
                          {status.results.length > 0 && (
                            <label
                              data-tutorial="results-approval"
                              style={{
                                display: "flex", alignItems: "center", gap: "8px",
                                padding: "6px 14px", borderRadius: "8px", cursor: "pointer",
                                fontSize: "0.8rem", fontWeight: 500,
                                border: gradesApproved ? "1px solid rgba(34,197,94,0.4)" : "1px solid rgba(245,158,11,0.3)",
                                background: gradesApproved ? "rgba(34,197,94,0.1)" : "rgba(245,158,11,0.08)",
                                color: gradesApproved ? "#4ade80" : "var(--text-secondary)",
                                transition: "all 0.2s",
                              }}
                            >
                              <input
                                type="checkbox"
                                checked={gradesApproved}
                                onChange={(e) => setGradesApproved(e.target.checked)}
                                style={{ accentColor: "#22c55e" }}
                              />
                              I have reviewed and approve these grades for export
                            </label>
                          )}
    </>
  );
}
