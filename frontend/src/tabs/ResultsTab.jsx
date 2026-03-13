import React, { useState, useRef, useEffect } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";

/*
 * Props required by ResultsTab:
 *
 * --- Helper functions (top-level, imported here or passed as props) ---
 * getAuthenticityStatus  - function(result) => { ai, plag, overallStatus }
 * getAIFlagColor         - function(flag) => { bg, text }
 * getPlagFlagColor       - function(flag) => { bg, text }
 *
 * --- State values ---
 * status                 - { results, is_running, log, complete }
 * config                 - full config object (assignments_folder, output_folder, roster_file, etc.)
 * rubric                 - rubric object
 * globalAINotes          - string
 * theme                  - "dark" | "light"
 * resultsFilter          - string
 * resultsPeriodFilter    - string
 * resultsAssignmentFilter - string
 * resultsSort            - { field, direction }
 * resultsSearch          - string
 * editedResults          - array
 * emailApprovals         - object { index: 'approved' | 'rejected' | 'pending' }
 * sentEmails             - object { index: true }
 * editedEmails           - object { index: { subject, body } }
 * emailStatus            - { sending, sent, failed, message }
 * autoApproveEmails      - boolean
 * gradesApproved         - boolean
 * savedAssignments       - array of assignment name strings
 * savedAssignmentData    - object { name: { aliases, title } }
 * studentAccommodations  - object { studentId: { presets, ... } }
 * sortedPeriods          - array of { filename, period_name }
 * portalSubmissions      - array
 * vportalConfigured      - boolean
 * batchExportLoading     - boolean
 * outlookExportLoading   - boolean
 * outlookSendStatus      - { status, sent, total, failed, message }
 * focusCommsStatus       - { status, sent, total, failed, skipped, message }
 * focusCommentsStatus    - { status, entered, total, failed, message }
 * curveModal             - { show, curveType, curveValue }
 * colWidths              - array | null
 * defaultColPercents     - array
 * pendingConfirmations   - number
 * pendingConfirmationStudents - array
 * confirmationStudentFilter   - string
 * ccParents              - boolean
 * focusExportModal       - boolean (value not used but setter is)
 * reviewModal            - { show, index }  (value not used but setter is)
 *
 * --- Setter functions ---
 * setResultsFilter
 * setResultsPeriodFilter
 * setResultsAssignmentFilter
 * setResultsSort
 * setResultsSearch
 * setStatus
 * setConfig
 * setEditedResults
 * setEmailApprovals
 * setSentEmails
 * setEditedEmails
 * setEmailStatus
 * setAutoApproveEmails
 * setGradesApproved
 * setBatchExportLoading
 * setOutlookExportLoading
 * setOutlookSendStatus
 * setOutlookSendPolling
 * setFocusCommsStatus
 * setFocusCommsPolling
 * setFocusCommentsStatus
 * setFocusCommentsPolling
 * setCurveModal
 * setFocusExportModal
 * setColWidths
 * setConfirmationStudentFilter
 * setCcParents
 *
 * --- Callbacks / functions ---
 * addToast               - function(message, type, duration?)
 * openResults            - function()
 * openReview             - function(index)
 * sendSingleEmail        - function(result, index)
 * getDefaultEmailBody    - function(index)
 * updateApprovalsBulk    - function(approvals)
 * initColWidths          - function()
 * handleResizeStart      - function(e, colIndex)
 *
 * --- Refs ---
 * tableRef               - React ref for table container
 * pendingConfirmationIds      - React ref
 * pendingConfirmationFilenames - React ref
 */

function ExportGradesDropdown({
  gradesApproved, batchExportLoading, setBatchExportLoading,
  editedResults, status, resultsAssignmentFilter, resultsPeriodFilter,
  setFocusExportModal, addToast,
}) {
  var _open = useState(false)
  var open = _open[0]
  var setOpen = _open[1]
  var _lmsLoading = useState(false)
  var lmsLoading = _lmsLoading[0]
  var setLmsLoading = _lmsLoading[1]
  var dropdownRef = useRef(null)

  // Close dropdown on outside click
  useEffect(function() {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return function() { document.removeEventListener('mousedown', handleClick) }
  }, [])

  function getFilteredResults() {
    var source = editedResults.length > 0 ? editedResults : status.results
    var filtered = source
    if (resultsAssignmentFilter) {
      filtered = filtered.filter(function(r) { return r.assignment === resultsAssignmentFilter })
    }
    if (resultsPeriodFilter) {
      filtered = filtered.filter(function(r) { return r.period === resultsPeriodFilter })
    }
    return filtered
  }

  function getAssignment() {
    var source = editedResults.length > 0 ? editedResults : status.results
    return resultsAssignmentFilter || (source[0] && source[0].assignment) || 'Assignment'
  }

  async function handleFocusSIS() {
    setOpen(false)
    setFocusExportModal(true)
  }

  async function handleFocusBatch() {
    setOpen(false)
    setBatchExportLoading(true)
    try {
      var resultsToExport = getFilteredResults()
      var assignment = getAssignment()
      var batchRes = await api.exportFocusBatch(resultsToExport, assignment)
      await api.exportFocusComments(resultsToExport, assignment)
      if (batchRes.error) {
        addToast(batchRes.error, "error")
      } else {
        var totalCount = batchRes.periods.reduce(function(sum, p) { return sum + p.count }, 0)
        addToast("Exported " + totalCount + " grades + comments to " + batchRes.periods.length + " period files", "success")
      }
    } catch (err) {
      addToast("Batch export error: " + err.message, "error")
    } finally {
      setBatchExportLoading(false)
    }
  }

  async function handleLmsExport(format) {
    setOpen(false)
    setLmsLoading(true)
    try {
      var resultsToExport = getFilteredResults()
      var assignment = getAssignment()
      var res = await api.exportLmsCsv(resultsToExport, assignment, 100, format)
      if (res.error) {
        addToast(res.error, "error")
      } else {
        var label = format === 'canvas' ? 'Canvas' : 'PowerSchool'
        addToast("Exported " + res.count + " grades as " + label + " CSV", "success")
      }
    } catch (err) {
      addToast(format + " export error: " + err.message, "error")
    } finally {
      setLmsLoading(false)
    }
  }

  var disabled = !gradesApproved || status.results.length === 0
  var loading = batchExportLoading || lmsLoading

  return (
    <div ref={dropdownRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        onClick={() => setOpen(!open)}
        className="btn btn-primary"
        disabled={disabled || loading}
        style={{
          background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
          opacity: gradesApproved ? 1 : 0.5,
          display: "flex", alignItems: "center", gap: "6px",
        }}
        title={gradesApproved ? "Export grades for LMS import" : "Approve grades first"}
      >
        <Icon name="Download" size={18} />
        {loading ? "Exporting..." : "Export Grades"}
        <Icon name="ChevronDown" size={14} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, marginTop: "4px",
          background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
          borderRadius: "8px", minWidth: "200px", zIndex: 1000,
          boxShadow: "0 8px 24px rgba(0,0,0,0.3)", overflow: "hidden",
        }}>
          <DropdownItem onClick={handleFocusSIS} icon="Upload" label="Focus SIS" />
          <DropdownItem onClick={handleFocusBatch} icon="FolderDown" label="Focus Batch" />
          <div style={{ height: "1px", background: "var(--glass-border)", margin: "2px 0" }} />
          <DropdownItem onClick={() => handleLmsExport('canvas')} icon="GraduationCap" label="Canvas LMS" />
          <DropdownItem onClick={() => handleLmsExport('powerschool')} icon="School" label="PowerSchool" />
        </div>
      )}
    </div>
  )
}

function DropdownItem({ onClick, icon, label }) {
  var _hover = useState(false)
  var hover = _hover[0]
  var setHover = _hover[1]
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        ...dropdownItemStyle,
        background: hover ? "rgba(99,102,241,0.1)" : "transparent",
      }}
    >
      <span style={{ display: "inline-flex", width: "20px", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={icon} size={16} />
      </span>
      {label}
    </button>
  )
}

var dropdownItemStyle = {
  display: "flex", alignItems: "center", gap: "10px",
  width: "100%", padding: "10px 16px", border: "none",
  background: "transparent", color: "var(--text-primary)",
  fontSize: "0.85rem", cursor: "pointer", textAlign: "left",
  lineHeight: "20px",
}

export default React.memo(function ResultsTab({
  // Helper functions passed as props
  getAuthenticityStatus,
  getAIFlagColor,
  getPlagFlagColor,
  // State
  status,
  config,
  rubric,
  globalAINotes,
  theme,
  resultsFilter,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  resultsSort,
  resultsSearch,
  editedResults,
  emailApprovals,
  sentEmails,
  editedEmails,
  emailStatus,
  autoApproveEmails,
  gradesApproved,
  savedAssignments,
  savedAssignmentData,
  studentAccommodations,
  sortedPeriods,
  portalSubmissions,
  vportalConfigured,
  batchExportLoading,
  outlookExportLoading,
  outlookSendStatus,
  focusCommsStatus,
  focusCommentsStatus,
  curveModal,
  colWidths,
  defaultColPercents,
  pendingConfirmations,
  pendingConfirmationStudents,
  confirmationStudentFilter,
  ccParents,
  // Setters
  setResultsFilter,
  setResultsPeriodFilter,
  setResultsAssignmentFilter,
  setResultsSort,
  setResultsSearch,
  setStatus,
  setConfig,
  setEditedResults,
  setEmailApprovals,
  setSentEmails,
  setEditedEmails,
  setEmailStatus,
  setAutoApproveEmails,
  setGradesApproved,
  setBatchExportLoading,
  setOutlookExportLoading,
  setOutlookSendStatus,
  setOutlookSendPolling,
  setFocusCommsStatus,
  setFocusCommsPolling,
  setFocusCommentsStatus,
  setFocusCommentsPolling,
  setCurveModal,
  setFocusExportModal,
  setColWidths,
  setConfirmationStudentFilter,
  setCcParents,
  // Callbacks
  addToast,
  openResults,
  openReview,
  sendSingleEmail,
  getDefaultEmailBody,
  updateApprovalsBulk,
  initColWidths,
  handleResizeStart,
  // Refs
  tableRef,
  pendingConfirmationIds,
  pendingConfirmationFilenames,
}) {
  return (
                <div
                  className="fade-in"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr",
                    gap: "20px",
                  }}
                >
                  {/* Results Table */}
                  <div data-tutorial="results-card" className="glass-card" style={{ padding: "25px" }}>
                    <div style={{ marginBottom: "20px" }}>
                      <h2
                        style={{
                          fontSize: "1.3rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          marginBottom: "15px",
                        }}
                      >
                        <Icon name="FileText" size={24} />
                        Grading Results (
                        {resultsFilter === "all" && !resultsPeriodFilter && !resultsAssignmentFilter
                          ? status.results.length
                          : status.results.filter((r, idx) => {
                              if (resultsFilter === "handwritten" && !r.is_handwritten)
                                return false;
                              if (resultsFilter === "typed" && r.is_handwritten)
                                return false;
                              if (resultsFilter === "verified" && r.marker_status !== "verified")
                                return false;
                              if (resultsFilter === "unverified" && r.marker_status !== "verified")
                                return false;
                              if (resultsFilter === "resubmission" && !r.is_resubmission)
                                return false;
                              if (resultsFilter === "approved" && emailApprovals[idx] !== "approved")
                                return false;
                              if (resultsFilter === "unapproved" && emailApprovals[idx] === "approved")
                                return false;
                              if (resultsPeriodFilter && r.period !== resultsPeriodFilter)
                                return false;
                              if (resultsAssignmentFilter && (r.assignment || r.filename) !== resultsAssignmentFilter)
                                return false;
                              return true;
                            }).length}
                        {(resultsFilter !== "all" || resultsPeriodFilter || resultsAssignmentFilter) &&
                          ` of ${status.results.length}`}
                        )
                      </h2>
                      {/* Assignment Stats - shows when assignment filter is active */}
                      {resultsAssignmentFilter && (() => {
                        const assignmentResults = status.results.filter(r => (r.assignment || r.filename) === resultsAssignmentFilter);
                        const gradedCount = assignmentResults.length;
                        const avgScore = gradedCount > 0 ? Math.round(assignmentResults.reduce((sum, r) => sum + (parseInt(r.score) || 0), 0) / gradedCount) : 0;
                        const gradeDistribution = { A: 0, B: 0, C: 0, D: 0, F: 0 };
                        assignmentResults.forEach(r => {
                          const grade = (r.letter_grade || "F")[0];
                          if (gradeDistribution[grade] !== undefined) gradeDistribution[grade]++;
                        });
                        const periodBreakdown = {};
                        assignmentResults.forEach(r => {
                          const period = r.period || "Unknown";
                          periodBreakdown[period] = (periodBreakdown[period] || 0) + 1;
                        });
                        return (
                          <div style={{
                            background: "rgba(99,102,241,0.1)",
                            border: "1px solid rgba(99,102,241,0.2)",
                            borderRadius: "10px",
                            padding: "12px 16px",
                            marginBottom: "15px",
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "20px",
                            alignItems: "center",
                            fontSize: "0.85rem"
                          }}>
                            <div>
                              <span style={{ color: "var(--text-muted)" }}>Graded:</span>{" "}
                              <strong>{gradedCount}</strong> students
                            </div>
                            <div>
                              <span style={{ color: "var(--text-muted)" }}>Avg Score:</span>{" "}
                              <strong style={{ color: avgScore >= 80 ? "#4ade80" : avgScore >= 70 ? "#fbbf24" : "#f87171" }}>{avgScore}%</strong>
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <span style={{ color: "var(--text-muted)" }}>Grades:</span>
                              {Object.entries(gradeDistribution).map(([grade, count]) => count > 0 && (
                                <span key={grade} style={{
                                  padding: "2px 8px",
                                  borderRadius: "4px",
                                  background: grade === "A" ? "rgba(74,222,128,0.2)" : grade === "B" ? "rgba(96,165,250,0.2)" : grade === "C" ? "rgba(251,191,36,0.2)" : "rgba(248,113,113,0.2)",
                                  color: grade === "A" ? "#4ade80" : grade === "B" ? "#60a5fa" : grade === "C" ? "#fbbf24" : "#f87171",
                                  fontWeight: 600
                                }}>
                                  {grade}: {count}
                                </span>
                              ))}
                            </div>
                            {Object.keys(periodBreakdown).length > 1 && (
                              <div style={{ display: "flex", gap: "8px" }}>
                                <span style={{ color: "var(--text-muted)" }}>By Period:</span>
                                {Object.entries(periodBreakdown).sort((a, b) => a[0].localeCompare(b[0])).map(([period, count]) => (
                                  <span key={period} style={{ padding: "2px 8px", borderRadius: "4px", background: "rgba(255,255,255,0.1)" }}>
                                    {period}: {count}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })()}
                      {status.results.length > 0 && (
                        <div
                          data-tutorial="results-filters"
                          style={{
                            display: "flex",
                            gap: "10px",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
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
                          <button
                            onClick={openResults}
                            className="btn btn-secondary"
                          >
                            <Icon name="FolderOpen" size={18} />
                            Open Folder
                          </button>
                          <button
                            onClick={async () => {
                              const hasAnyFilter = resultsFilter !== "all" || resultsPeriodFilter || resultsAssignmentFilter || resultsSearch.trim();

                              // Collect filenames of currently visible results
                              const visibleFilenames = [];
                              const searchLower = resultsSearch.trim().toLowerCase();
                              status.results.forEach((r, idx) => {
                                if (resultsFilter === "handwritten" && !r.is_handwritten) return;
                                if (resultsFilter === "typed" && r.is_handwritten) return;
                                if (resultsFilter === "verified" && r.marker_status !== "verified") return;
                                if (resultsFilter === "unverified" && r.marker_status !== "unverified") return;
                                if (resultsFilter === "mismatched" && !r.config_mismatch) return;
                                if (resultsFilter === "resubmission" && !r.is_resubmission) return;
                                if (resultsFilter === "approved" && emailApprovals[idx] !== "approved") return;
                                if (resultsFilter === "unapproved" && emailApprovals[idx] === "approved") return;
                                if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
                                if (resultsAssignmentFilter && (r.assignment || r.filename) !== resultsAssignmentFilter) return;
                                if (searchLower && !(
                                  (r.student_name || "").toLowerCase().includes(searchLower) ||
                                  (r.assignment || "").toLowerCase().includes(searchLower)
                                )) return;
                                if (r.filename) visibleFilenames.push(r.filename);
                              });

                              const clearCount = hasAnyFilter ? visibleFilenames.length : status.results.length;
                              const confirmMsg = hasAnyFilter
                                ? "Clear " + clearCount + " filtered results? This cannot be undone."
                                : "Clear all " + clearCount + " grading results? This cannot be undone.";

                              if (confirm(confirmMsg)) {
                                try {
                                  if (hasAnyFilter && visibleFilenames.length > 0) {
                                    // Clear only the visible results by filename
                                    await api.clearResults(visibleFilenames);
                                    const filenameSet = new Set(visibleFilenames);
                                    setStatus((prev) => ({
                                      ...prev,
                                      results: prev.results.filter(r => !filenameSet.has(r.filename)),
                                    }));
                                    setEditedResults((prev) =>
                                      prev.filter(r => !filenameSet.has(r.filename))
                                    );
                                    // Clear approvals/emails for removed results
                                    const removedIndices = new Set();
                                    status.results.forEach((r, i) => {
                                      if (filenameSet.has(r.filename)) removedIndices.add(i);
                                    });
                                    setEmailApprovals((prev) => {
                                      const updated = { ...prev };
                                      removedIndices.forEach(i => delete updated[i]);
                                      return updated;
                                    });
                                    setEditedEmails((prev) => {
                                      const updated = { ...prev };
                                      removedIndices.forEach(i => delete updated[i]);
                                      return updated;
                                    });
                                    addToast("Cleared " + visibleFilenames.length + " results", "success");
                                  } else if (!hasAnyFilter) {
                                    // Clear everything
                                    await api.clearResults();
                                    setStatus((prev) => ({
                                      ...prev,
                                      results: [],
                                      log: [],
                                      complete: false,
                                    }));
                                    setEditedResults([]);
                                    setEmailApprovals({});
                                    setEditedEmails({});
                                    addToast("Cleared all results", "success");
                                  }
                                } catch (e) {
                                  addToast(
                                    "Error clearing results: " + e.message,
                                    "error",
                                  );
                                }
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ background: "rgba(239,68,68,0.2)" }}
                          >
                            <Icon name="Trash2" size={18} />
                            {(resultsFilter !== "all" || resultsPeriodFilter || resultsAssignmentFilter || resultsSearch.trim()) ? "Clear Filtered" : "Clear All"}
                          </button>
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
                          {/* Email Actions Group */}
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
                        </div>
                      )}
                    </div>

                    {/* Outlook Send Progress */}
                    {outlookSendStatus.status === "running" && (
                      <div style={{
                        padding: "12px 16px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--glass-border)",
                        marginTop: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.85rem", marginBottom: "6px", color: "var(--text-secondary)" }}>
                            {outlookSendStatus.message}
                          </div>
                          <div style={{ height: "6px", background: "var(--glass-border)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: (outlookSendStatus.total > 0 ? (outlookSendStatus.sent / outlookSendStatus.total * 100) : 0) + "%",
                              background: "var(--primary)",
                              borderRadius: "3px",
                              transition: "width 0.3s ease",
                            }} />
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                            {outlookSendStatus.sent + " of " + outlookSendStatus.total + " sent"}
                            {outlookSendStatus.failed > 0 ? " (" + outlookSendStatus.failed + " failed)" : ""}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Focus Comms Send Progress */}
                    {focusCommsStatus.status === "running" && (
                      <div style={{
                        padding: "12px 16px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--glass-border)",
                        marginTop: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.85rem", marginBottom: "6px", color: "var(--text-secondary)" }}>
                            {"Focus: " + focusCommsStatus.message}
                          </div>
                          <div style={{ height: "6px", background: "var(--glass-border)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: (focusCommsStatus.total > 0 ? (focusCommsStatus.sent / focusCommsStatus.total * 100) : 0) + "%",
                              background: "#10b981",
                              borderRadius: "3px",
                              transition: "width 0.3s ease",
                            }} />
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                            {focusCommsStatus.sent + " of " + focusCommsStatus.total + " sent"}
                            {focusCommsStatus.failed > 0 ? " (" + focusCommsStatus.failed + " failed)" : ""}
                          </div>
                        </div>
                        <button onClick={() => { api.stopFocusComms(); }} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>Stop</button>
                      </div>
                    )}

                    {/* Authenticity Summary Alert */}
                    {status.results.length > 0 &&
                      (() => {
                        const authStats = status.results.reduce(
                          (acc, r) => {
                            const auth = getAuthenticityStatus(r);
                            if (auth.ai.flag === "likely") acc.aiLikely++;
                            else if (auth.ai.flag === "possible")
                              acc.aiPossible++;
                            if (auth.plag.flag === "likely") acc.plagLikely++;
                            else if (auth.plag.flag === "possible")
                              acc.plagPossible++;
                            return acc;
                          },
                          {
                            aiLikely: 0,
                            aiPossible: 0,
                            plagLikely: 0,
                            plagPossible: 0,
                          },
                        );

                        const hasConcerns =
                          authStats.aiLikely +
                            authStats.aiPossible +
                            authStats.plagLikely +
                            authStats.plagPossible >
                          0;

                        return hasConcerns ? (
                          <div
                            style={{
                              marginBottom: "20px",
                              padding: "15px 20px",
                              borderRadius: "12px",
                              background:
                                "linear-gradient(135deg, rgba(248,113,113,0.1), rgba(251,191,36,0.1))",
                              border: "1px solid rgba(248,113,113,0.3)",
                              display: "flex",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "15px",
                            }}
                          >
                            <Icon
                              name="Shield"
                              size={24}
                              style={{ color: "#f87171" }}
                            />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div
                                style={{ fontWeight: 700, marginBottom: "8px" }}
                              >
                                Authenticity Summary
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: "20px",
                                  fontSize: "0.9rem",
                                }}
                              >
                                {/* AI Detection Stats */}
                                <div>
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Bot"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
                                    AI Detection
                                  </div>
                                  <div style={{ display: "flex", gap: "10px" }}>
                                    {authStats.aiLikely > 0 && (
                                      <span style={{ color: "#f87171" }}>
                                        {authStats.aiLikely} likely
                                      </span>
                                    )}
                                    {authStats.aiPossible > 0 && (
                                      <span style={{ color: "#fbbf24" }}>
                                        {authStats.aiPossible} possible
                                      </span>
                                    )}
                                    {authStats.aiLikely === 0 &&
                                      authStats.aiPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
                                      )}
                                  </div>
                                </div>
                                {/* Plagiarism Stats */}
                                <div>
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Copy"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
                                    Plagiarism
                                  </div>
                                  <div style={{ display: "flex", gap: "10px" }}>
                                    {authStats.plagLikely > 0 && (
                                      <span style={{ color: "#f87171" }}>
                                        {authStats.plagLikely} likely
                                      </span>
                                    )}
                                    {authStats.plagPossible > 0 && (
                                      <span style={{ color: "#fbbf24" }}>
                                        {authStats.plagPossible} possible
                                      </span>
                                    )}
                                    {authStats.plagLikely === 0 &&
                                      authStats.plagPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
                                      )}
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              Hover for details
                            </div>
                          </div>
                        ) : null;
                      })()}

                    {/* Auto-Approve Toggle */}
                    {status.results.length > 0 && (
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
                    )}

                    {emailStatus.message && (
                      <div
                        style={{
                          marginBottom: "15px",
                          padding: "12px 15px",
                          background: emailStatus.message.includes("Error")
                            ? "rgba(248,113,113,0.1)"
                            : "rgba(74,222,128,0.1)",
                          borderRadius: "8px",
                          border: emailStatus.message.includes("Error")
                            ? "1px solid rgba(248,113,113,0.3)"
                            : "1px solid rgba(74,222,128,0.3)",
                        }}
                      >
                        {emailStatus.message}
                      </div>
                    )}

                    {/* Portal Submissions Section */}
                    {portalSubmissions.length > 0 && (resultsFilter === "all" || resultsFilter === "portal_pending") && (
                      <div style={{
                        background: "rgba(30,41,59,0.5)", borderRadius: "12px",
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
                    )}

                    {status.results.length === 0 && portalSubmissions.length === 0 ? (
                      <p
                        style={{
                          color: "var(--text-secondary)",
                          textAlign: "center",
                          padding: "40px",
                        }}
                      >
                        No results yet. Grade some assignments first.
                      </p>
                    ) : (
                      <>
                        {/* Search Input */}
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
                                  <tr
                                    key={r.filename || i}
                                    style={{
                                      background: r.edited
                                        ? "rgba(251,191,36,0.1)"
                                        : "transparent",
                                    }}
                                  >
                                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                      <div
                                        style={{
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "4px",
                                          overflow: "hidden",
                                        }}
                                      >
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.student_name}</span>
                                        {r.is_handwritten && (
                                          <span
                                            title="Handwritten/Scanned Assignment"
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(16, 185, 129, 0.15)",
                                              color: "#10b981",
                                            }}
                                          >
                                            <Icon name="PenTool" size={12} />
                                          </span>
                                        )}
                                        {r.marker_status === "unverified" && (
                                          <span
                                            title="UNVERIFIED: No markers or config found. Grade may be inaccurate. Set up assignment config and regrade."
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(251, 191, 36, 0.2)",
                                              color: "#fbbf24",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon
                                              name="AlertTriangle"
                                              size={12}
                                            />
                                          </span>
                                        )}
                                        {r.config_mismatch && (
                                          <span
                                            title={r.config_mismatch_reason || "CONFIG MISMATCH: This submission doesn't match any saved assignment. Grade may be incorrect!"}
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background: "rgba(239, 68, 68, 0.2)",
                                              color: "#ef4444",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon name="FileX" size={12} />
                                          </span>
                                        )}
                                        {r.is_resubmission && (
                                          <span
                                            title={r.kept_higher
                                              ? "RESUBMISSION: Kept original grade (" + r.score + "). New submission scored " + r.resubmission_score + "."
                                              : r.previous_score != null
                                                ? "RESUBMISSION: Improved from " + r.previous_score + " \u2192 " + r.score
                                                : "RESUBMISSION: This is a newer version of a previously graded assignment."
                                            }
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background: r.kept_higher
                                                ? "rgba(251, 191, 36, 0.15)"
                                                : "rgba(59, 130, 246, 0.15)",
                                              color: r.kept_higher ? "#fbbf24" : "#3b82f6",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon
                                              name={r.kept_higher ? "ShieldCheck" : "RefreshCw"}
                                              size={12}
                                            />
                                          </span>
                                        )}
                                        {r.student_id &&
                                          studentAccommodations[
                                            r.student_id
                                          ] && (
                                            <span
                                              title={
                                                "Accommodations: " +
                                                (studentAccommodations[
                                                  r.student_id
                                                ]?.presets
                                                  ?.map((p) => p.name)
                                                  .join(", ") || "Custom")
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                width: "20px",
                                                height: "20px",
                                                borderRadius: "4px",
                                                background:
                                                  "rgba(244, 114, 182, 0.15)",
                                                color: "#f472b6",
                                                cursor: "help",
                                              }}
                                            >
                                              <Icon name="Heart" size={12} />
                                            </span>
                                          )}
                                      </div>
                                    </td>
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
                                    <td style={{ textAlign: "center" }}>
                                      {(() => {
                                        const auth = getAuthenticityStatus(r);
                                        const aiColor = getAIFlagColor(
                                          auth.ai.flag,
                                        );
                                        const plagColor = getPlagFlagColor(
                                          auth.plag.flag,
                                        );
                                        const studentId = r.student_id || r.student;
                                        const isTrusted = (config.trustedStudents || []).includes(studentId);
                                        const isFlagged = auth.ai.flag !== "none" || auth.plag.flag !== "none";

                                        // If student is trusted, show trusted badge instead
                                        if (isTrusted) {
                                          return (
                                            <div style={{ display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-start" }}>
                                              <span
                                                title="This student is marked as trusted - detection flags are overridden"
                                                style={{
                                                  display: "inline-flex",
                                                  alignItems: "center",
                                                  gap: "4px",
                                                  padding: "3px 8px",
                                                  borderRadius: "12px",
                                                  fontWeight: 500,
                                                  background: "rgba(34,197,94,0.2)",
                                                  color: "#22c55e",
                                                  fontSize: "0.75rem",
                                                }}
                                              >
                                                <Icon name="ShieldCheck" size={12} />
                                                Trusted Writer
                                              </span>
                                              <button
                                                onClick={() => {
                                                  setConfig(prev => ({
                                                    ...prev,
                                                    trustedStudents: prev.trustedStudents.filter(id => id !== studentId)
                                                  }));
                                                  addToast(`Removed ${r.student} from trusted list`, "info");
                                                }}
                                                style={{
                                                  background: "none",
                                                  border: "none",
                                                  color: "var(--text-muted)",
                                                  fontSize: "0.7rem",
                                                  cursor: "pointer",
                                                  padding: "2px 4px",
                                                }}
                                              >
                                                Remove trust
                                              </button>
                                            </div>
                                          );
                                        }

                                        return (
                                          <div
                                            style={{
                                              display: "flex",
                                              flexDirection: "column",
                                              gap: "4px",
                                            }}
                                          >
                                            {/* AI Detection */}
                                            <span
                                              title={
                                                auth.ai.reason ||
                                                `AI: ${auth.ai.flag}${auth.ai.confidence ? ` (${auth.ai.confidence}%)` : ""}`
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "4px",
                                                padding: "3px 8px",
                                                borderRadius: "12px",
                                                fontWeight: 500,
                                                background: aiColor.bg,
                                                color: aiColor.text,
                                                fontSize: "0.75rem",
                                                cursor: auth.ai.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.ai.flag === "likely"
                                                    ? "Bot"
                                                    : auth.ai.flag ===
                                                        "possible"
                                                      ? "Bot"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              AI:{" "}
                                              {auth.ai.flag === "none"
                                                ? "Clear"
                                                : auth.ai.flag}
                                              {auth.ai.confidence > 0 &&
                                                ` ${auth.ai.confidence}%`}
                                            </span>
                                            {/* Plagiarism Detection */}
                                            <span
                                              title={
                                                auth.plag.reason ||
                                                `Plagiarism: ${auth.plag.flag}`
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "4px",
                                                padding: "3px 8px",
                                                borderRadius: "12px",
                                                fontWeight: 500,
                                                background: plagColor.bg,
                                                color: plagColor.text,
                                                fontSize: "0.75rem",
                                                cursor: auth.plag.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.plag.flag === "likely"
                                                    ? "Copy"
                                                    : auth.plag.flag ===
                                                        "possible"
                                                      ? "Copy"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              Copy:{" "}
                                              {auth.plag.flag === "none"
                                                ? "Clear"
                                                : auth.plag.flag}
                                            </span>
                                            {/* Trust button for flagged students -- adds to trusted list AND regrades */}
                                            {isFlagged && (
                                              <button
                                                onClick={async () => {
                                                  var newTrusted = [...(config.trustedStudents || []), studentId];
                                                  setConfig(prev => ({
                                                    ...prev,
                                                    trustedStudents: newTrusted
                                                  }));
                                                  addToast("Trusting " + r.student_name + " and regrading...", "info");
                                                  try {
                                                    await api.deleteResult(r.filename);
                                                    setStatus(function(prev) { return { ...prev, results: prev.results.filter(function(res) { return res.filename !== r.filename; }) }; });
                                                    var filename = r.original_filename || r.filename;
                                                    var trustAssignmentCfg = savedAssignmentData[r.assignment] || Object.values(savedAssignmentData).find(function(c) { return c.title === r.assignment; }) || null;
                                                    await api.startGrading({
                                                      assignments_folder: config.assignments_folder,
                                                      output_folder: config.output_folder,
                                                      roster_file: config.roster_file,
                                                      grading_period: config.grading_period,
                                                      grade_level: config.grade_level,
                                                      subject: config.subject,
                                                      teacher_name: config.teacher_name,
                                                      school_name: config.school_name,
                                                      ai_model: config.ai_model,
                                                      extraction_mode: config.extraction_mode,
                                                      selectedFiles: [filename],
                                                      globalAINotes: globalAINotes,
                                                      classPeriod: r.period || '',
                                                      ensemble_models: config.ensemble_enabled && config.ensemble_models?.length >= 2 ? config.ensemble_models : null,
                                                      trustedStudents: newTrusted,
                                                      gradingStyle: rubric.gradingStyle || 'standard',
                                                      assignmentConfig: trustAssignmentCfg,
                                                      rubric: rubric,
                                                    });
                                                    var checkInterval = setInterval(async function() {
                                                      var st = await api.getStatus();
                                                      if (!st.is_running) {
                                                        clearInterval(checkInterval);
                                                        if (st.results && st.results.length > 0) {
                                                          var newResult = st.results.find(function(res) {
                                                            return res.student_name === r.student_name && (res.assignment === r.assignment || res.filename === filename);
                                                          });
                                                          if (newResult) {
                                                            setStatus(function(prev) { return { ...prev, results: [...prev.results, newResult] }; });
                                                            addToast(r.student_name + " regraded: " + newResult.letter_grade + " (" + newResult.score + "%)", "success");
                                                          }
                                                        }
                                                      }
                                                    }, 1000);
                                                  } catch (err) {
                                                    addToast("Regrade failed: " + err.message, "error");
                                                  }
                                                }}
                                                title="Mark as trusted writer - this student writes well naturally"
                                                style={{
                                                  background: "rgba(34,197,94,0.1)",
                                                  border: "1px solid rgba(34,197,94,0.3)",
                                                  color: "#22c55e",
                                                  fontSize: "0.7rem",
                                                  cursor: "pointer",
                                                  padding: "2px 6px",
                                                  borderRadius: "4px",
                                                  display: "inline-flex",
                                                  alignItems: "center",
                                                  gap: "3px",
                                                }}
                                              >
                                                <Icon name="ShieldCheck" size={10} />
                                                Trust
                                              </button>
                                            )}
                                          </div>
                                        );
                                      })()}
                                    </td>
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
                                        onClick={async (e) => {
                                          e.stopPropagation();
                                          if (!confirm(`Regrade "${r.student_name}"'s assignment? This will delete the previous grade.`)) return;
                                          try {
                                            // Delete the previous result first
                                            await api.deleteResult(r.filename);
                                            setStatus((prev) => ({
                                              ...prev,
                                              results: prev.results.filter((res) => res.filename !== r.filename),
                                            }));
                                            addToast(`Regrading ${r.student_name}...`, "info");
                                            // Use the original filename to regrade
                                            const filename = r.original_filename || r.filename;
                                            var regradeAssignmentCfg = savedAssignmentData[r.assignment] || Object.values(savedAssignmentData).find(function(c) { return c.title === r.assignment; }) || null;
                                            await api.startGrading({
                                              assignments_folder: config.assignments_folder,
                                              output_folder: config.output_folder,
                                              roster_file: config.roster_file,
                                              grading_period: config.grading_period,
                                              grade_level: config.grade_level,
                                              subject: config.subject,
                                              teacher_name: config.teacher_name,
                                              school_name: config.school_name,
                                              ai_model: config.ai_model,
                                              extraction_mode: config.extraction_mode,
                                              selectedFiles: [filename],
                                              globalAINotes: globalAINotes,
                                              classPeriod: r.period || '',
                                              ensemble_models: config.ensemble_enabled && config.ensemble_models?.length >= 2 ? config.ensemble_models : null,
                                              trustedStudents: config.trustedStudents || [],
                                              gradingStyle: rubric.gradingStyle || 'standard',
                                              assignmentConfig: regradeAssignmentCfg,
                                              rubric: rubric,
                                            });
                                            // Poll for completion and update results
                                            const checkStatus = setInterval(async () => {
                                              const st = await api.getStatus();
                                              if (!st.is_running) {
                                                clearInterval(checkStatus);
                                                if (st.results && st.results.length > 0) {
                                                  const newResult = st.results.find(res =>
                                                    res.student_name === r.student_name &&
                                                    (res.assignment === r.assignment || res.filename === filename)
                                                  );
                                                  if (newResult) {
                                                    setStatus(prev => ({ ...prev, results: [...prev.results, newResult] }));
                                                    addToast(`Regraded ${r.student_name}: ${newResult.letter_grade} (${newResult.score}%)`, "success");
                                                  }
                                                }
                                              }
                                            }, 1000);
                                          } catch (err) {
                                            addToast(`Regrade failed: ${err.message}`, "error");
                                          }
                                        }}
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
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                        </div>

                        {/* Send Approved Emails Button */}
                        {Object.values(emailApprovals).filter(
                          (v) => v === "approved",
                        ).length > 0 &&
                          !autoApproveEmails && (
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
                          )}
                      </>
                    )}
                  </div>
                </div>
  );
});
