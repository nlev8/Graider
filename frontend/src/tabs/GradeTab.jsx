import React, { useState, useEffect, useRef } from "react";
import Icon from "../components/Icon";
import ActivityLog from "../components/ActivityLog";
import * as api from "../services/api";

/*
 * Grade tab — JSX + (after PR 2) toggle/log local state.
 *
 * Per docs/superpowers/plans/2026-05-03-grade-tab-extraction.md, this is the
 * extracted Grade tab. PR 1 was the pure JSX lift; PR 2 (this revision) moves
 * pure UI toggles + the showActivityLog vertical slice (state + ref + 2 effects)
 * into the component. Future PRs (3-4) move the individual-upload slice and the
 * student-filter cleanup.
 *
 * Mount: this component is always-mounted with display:none-style hiding from
 * App.jsx (Assistant-tab precedent), so local state survives tab switches.
 *
 * Closures the JSX still captures (props):
 *   --- App-shell state (read-only) ---
 *   status, config
 *   savedAssignments, savedAssignmentData, periods, sortedPeriods, periodStudents
 *   availableFiles, emailApprovals
 *   MODEL_COST_PER_ASSIGNMENT (App-local constant; could lift to a util later)
 *
 *   --- App-shell mutators ---
 *   setStatus               - Used by error-banner Dismiss
 *   setSavedAssignmentData  - SHARED MUTABLE state (Codex Round 2 #4); written
 *                             from completion-only toggle and due-date editor.
 *
 *   --- Grade-specific state (will move to GradeTab in PR 3-4) ---
 *   selectedPeriod / setSelectedPeriod
 *   gradeFilterStudent / setGradeFilterStudent
 *   gradeFilterAssignment / setGradeFilterAssignment
 *   selectedFiles / setSelectedFiles
 *   individualUpload / setIndividualUpload
 *   setGradeAssignment / setGradeImportedDoc  - written from the assignment-filter loader
 *
 *   --- Handlers/helpers (will move to GradeTab in PR 3) ---
 *   loadPeriodStudents
 *   getStudentSuggestions
 *   handleIndividualFileSelect
 *   handleIndividualGrade
 *   clearIndividualUpload
 *   addToast                - App-shell utility, stays in App
 *
 * GradeTab-owned (PR 2):
 *   gradingModesExpanded, showActivityLog
 *   skipVerified, excludeGradedStudents, excludeApprovedStudents
 *   logRef
 *   auto-scroll log effect
 *   auto-expand-Activity-Monitor-on-error effect
 */

export default function GradeTab(props) {
  const {
    status,
    config,
    savedAssignments,
    savedAssignmentData,
    setSavedAssignmentData,
    setStatus,
    addToast,
    periods,
    selectedPeriod,
    setSelectedPeriod,
    setGradeFilterStudent,
    loadPeriodStudents,
    sortedPeriods,
    periodStudents,
    gradeFilterStudent,
    gradeFilterAssignment,
    setGradeFilterAssignment,
    setGradeAssignment,
    setGradeImportedDoc,
    availableFiles,
    selectedFiles,
    setSelectedFiles,
    emailApprovals,
    individualUpload,
    setIndividualUpload,
    getStudentSuggestions,
    handleIndividualFileSelect,
    handleIndividualGrade,
    clearIndividualUpload,
    MODEL_COST_PER_ASSIGNMENT,
  } = props;

  // PR 2 — local Grade-tab state (pure toggles + showActivityLog vertical slice).
  const [gradingModesExpanded, setGradingModesExpanded] = useState(false);
  const [showActivityLog, setShowActivityLog] = useState(false);
  const [skipVerified, setSkipVerified] = useState(false);
  const [excludeGradedStudents, setExcludeGradedStudents] = useState(false);
  const [excludeApprovedStudents, setExcludeApprovedStudents] = useState(false);
  const logRef = useRef(null);

  // Auto-scroll the activity log to the bottom when new entries arrive.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status.log]);

  // Auto-expand the Activity Monitor when an error occurs so the user sees it.
  useEffect(() => {
    if (status.error) {
      setShowActivityLog(true);
    }
  }, [status.error]);

  const pct = status.total > 0 ? (status.progress / status.total) * 100 : 0;

  return (
    <div data-tutorial="grade-card" className="fade-in">
      {/* Error Alert Banner */}
      {status.error && (
        <div
          className="glass-card fade-in"
          style={{
            padding: "15px 20px",
            marginBottom: "20px",
            background: "rgba(248,113,113,0.1)",
            border: "1px solid rgba(248,113,113,0.4)",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <Icon
            name="AlertTriangle"
            size={24}
            style={{ color: "#f87171" }}
          />
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontWeight: 600,
                color: "#f87171",
                marginBottom: "4px",
              }}
            >
              Grading Stopped - Error Detected
            </div>
            <div
              style={{
                fontSize: "0.9rem",
                color: "var(--text-secondary)",
              }}
            >
              {status.error}
            </div>
          </div>
          <button
            onClick={() =>
              setStatus((prev) => ({ ...prev, error: null }))
            }
            style={{
              background: "rgba(248,113,113,0.2)",
              border: "none",
              borderRadius: "8px",
              padding: "8px 12px",
              color: "#f87171",
              cursor: "pointer",
              fontSize: "0.85rem",
              fontWeight: 500,
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Assignment Grading Modes - Collapsible */}
      {savedAssignments.length > 0 && (
        <div
          className="glass-card"
          style={{
            padding: gradingModesExpanded ? "15px 20px" : "12px 20px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
            }}
            onClick={() => setGradingModesExpanded(!gradingModesExpanded)}
          >
            <h3
              style={{
                fontSize: "1rem",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: "10px",
                margin: 0,
              }}
            >
              <Icon
                name={gradingModesExpanded ? "ChevronDown" : "ChevronRight"}
                size={18}
              />
              <Icon name="FileCheck" size={18} style={{ color: "#10b981" }} />
              Assignment Grading Modes
              <span
                style={{
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                  fontWeight: 400,
                }}
              >
                ({savedAssignments.filter(n => savedAssignmentData[n]?.completionOnly).length} completion-only)
              </span>
            </h3>
          </div>

          {gradingModesExpanded && (
            <div style={{ marginTop: "15px" }}>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "12px",
                }}
              >
                Toggle assignments between AI grading and completion-only tracking.
              </p>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  maxHeight: "250px",
                  overflowY: "auto",
                }}
              >
                {savedAssignments.map((name) => {
                  const isCompletionOnly = savedAssignmentData[name]?.completionOnly || false;
                  return (
                    <div
                      key={name}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "10px 12px",
                        borderRadius: "8px",
                        background: isCompletionOnly
                          ? "rgba(34, 197, 94, 0.1)"
                          : "rgba(99, 102, 241, 0.05)",
                        border: isCompletionOnly
                          ? "1px solid rgba(34, 197, 94, 0.3)"
                          : "1px solid var(--glass-border)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon
                          name={isCompletionOnly ? "CheckCircle" : "FileText"}
                          size={18}
                          style={{ color: isCompletionOnly ? "#22c55e" : "#6366f1" }}
                        />
                        <span style={{ fontWeight: 500 }}>{name}</span>
                        {isCompletionOnly && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              background: "rgba(34, 197, 94, 0.2)",
                              color: "#22c55e",
                              padding: "2px 8px",
                              borderRadius: "10px",
                              fontWeight: 600,
                            }}
                          >
                            COMPLETION
                          </span>
                        )}
                      </div>
                      <button
                        className="btn"
                        onClick={async (e) => {
                          e.stopPropagation();
                          const newData = {
                            ...savedAssignmentData[name],
                            completionOnly: !isCompletionOnly,
                          };
                          setSavedAssignmentData(prev => ({
                            ...prev,
                            [name]: newData,
                          }));
                          try {
                            // Load the full assignment first to preserve all data (including importedDoc)
                            const fullData = await api.loadAssignment(name);
                            if (fullData.assignment) {
                              await api.saveAssignmentConfig({
                                ...fullData.assignment,
                                completionOnly: !isCompletionOnly,
                              });
                            } else {
                              // Fallback if load fails
                              await api.saveAssignmentConfig({
                                ...newData,
                                title: name,
                                completionOnly: !isCompletionOnly,
                              });
                            }
                            addToast(
                              `"${name}" set to ${!isCompletionOnly ? "Completion Only" : "AI Grading"}`,
                              "success"
                            );
                          } catch (e) {
                            addToast("Error saving: " + e.message, "error");
                          }
                        }}
                        style={{
                          padding: "6px 12px",
                          fontSize: "0.8rem",
                          background: isCompletionOnly ? "rgba(34, 197, 94, 0.2)" : "rgba(99, 102, 241, 0.2)",
                          color: isCompletionOnly ? "#22c55e" : "#818cf8",
                          border: `1px solid ${isCompletionOnly ? "rgba(34, 197, 94, 0.4)" : "rgba(99, 102, 241, 0.4)"}`,
                        }}
                        title={isCompletionOnly ? "Click to enable AI grading" : "Click to set as completion only"}
                      >
                        <Icon name={isCompletionOnly ? "CheckCircle" : "Sparkles"} size={14} style={{ marginRight: "6px" }} />
                        {isCompletionOnly ? "Completion Only" : "AI Grading"}
                      </button>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <Icon name="Clock" size={14} style={{ color: (() => { const dd = savedAssignmentData[name]?.dueDate; if (!dd) return "var(--text-muted)"; return new Date(dd) < new Date() ? "#f87171" : "#fbbf24"; })() }} />
                        <input
                          type="date"
                          className="input"
                          value={(savedAssignmentData[name]?.dueDate || "").slice(0, 10)}
                          onChange={async (e) => {
                            const dateVal = e.target.value ? e.target.value + "T23:59" : "";
                            setSavedAssignmentData(prev => ({ ...prev, [name]: { ...prev[name], dueDate: dateVal } }));
                            try {
                              const fullData = await api.loadAssignment(name);
                              if (fullData.assignment) {
                                await api.saveAssignmentConfig({ ...fullData.assignment, dueDate: dateVal });
                              }
                              addToast(dateVal ? "Due date set for " + name : "Due date cleared for " + name, "success");
                            } catch (err) {
                              addToast("Error saving due date: " + err.message, "error");
                            }
                          }}
                          style={{ width: "130px", fontSize: "0.75rem", padding: "4px 6px", height: "30px" }}
                          title={savedAssignmentData[name]?.dueDate ? "Due: " + new Date(savedAssignmentData[name].dueDate).toLocaleDateString() : "Set due date"}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Activity Monitor - Horizontal Collapsible */}
      <div
        className="glass-card"
        style={{
          padding: "15px 20px",
          marginBottom: "20px",
          background: status.error
            ? "rgba(248,113,113,0.05)"
            : status.is_running
              ? "rgba(74,222,128,0.05)"
              : "var(--glass-bg)",
          border: `1px solid ${
            status.error
              ? "rgba(248,113,113,0.3)"
              : status.is_running
                ? "rgba(74,222,128,0.3)"
                : "var(--glass-border)"
          }`,
        }}
      >
        <button
          onClick={() => setShowActivityLog(!showActivityLog)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--text-primary)",
            padding: 0,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <Icon
              name={status.error ? "AlertCircle" : "Terminal"}
              size={18}
              style={{
                color: status.error
                  ? "#f87171"
                  : status.is_running
                    ? "#4ade80"
                    : "var(--text-secondary)",
              }}
            />
            <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
              Activity Monitor
            </span>
            {status.error && (
              <span
                style={{
                  fontSize: "0.75rem",
                  padding: "3px 10px",
                  borderRadius: "12px",
                  background: "rgba(248,113,113,0.2)",
                  color: "#f87171",
                  fontWeight: 500,
                }}
              >
                Error
              </span>
            )}
            {status.is_running && !status.error && (
              <span
                style={{
                  fontSize: "0.75rem",
                  padding: "3px 10px",
                  borderRadius: "12px",
                  background: "rgba(74,222,128,0.2)",
                  color: "#4ade80",
                  fontWeight: 500,
                }}
              >
                Running...
              </span>
            )}
            {status.log.length > 0 && (
              <span
                style={{
                  fontSize: "0.75rem",
                  padding: "3px 8px",
                  borderRadius: "8px",
                  background: "var(--input-bg)",
                  color: "var(--text-muted)",
                }}
              >
                {status.log.length} entries
              </span>
            )}
          </div>
          <Icon
            name={showActivityLog ? "ChevronUp" : "ChevronDown"}
            size={18}
            style={{ color: "var(--text-muted)" }}
          />
        </button>

        <ActivityLog
          ref={logRef}
          open={showActivityLog}
          log={status.log}
        />
      </div>

      {/* Full width layout */}
      <div className="glass-card" style={{ padding: "25px" }}>
        <h2
          style={{
            fontSize: "1.3rem",
            fontWeight: 700,
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Icon name="Play" size={24} />
          Start Grading
        </h2>

        {/* Period Filter - Show when periods exist */}
        {periods.length > 0 && (
          <div
            data-tutorial="grade-period-filter"
            style={{
              padding: "15px",
              background:
                "linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.05))",
              borderRadius: "12px",
              border: "1px solid rgba(99, 102, 241, 0.2)",
              marginBottom: "20px",
            }}
          >
            <label
              className="label"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Icon
                name="Users"
                size={16}
                style={{ color: "var(--accent-primary)" }}
              />
              Filter by Class Period
            </label>
            <select
              className="input"
              value={selectedPeriod}
              onChange={async (e) => {
                const periodFilename = e.target.value;
                setSelectedPeriod(periodFilename);
                setGradeFilterStudent(""); // Clear student filter when period changes
                await loadPeriodStudents(periodFilename);
              }}
              style={{ cursor: "pointer" }}
            >
              <option value="">All Periods (No Filter)</option>
              {sortedPeriods.map((p) => (
                <option key={p.filename} value={p.filename}>
                  {p.period_name} ({p.row_count} students)
                </option>
              ))}
            </select>
            {selectedPeriod && periodStudents.length > 0 && (
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "var(--accent-primary)",
                  marginTop: "8px",
                  fontWeight: 500,
                }}
              >
                ✓ Filtering to {periodStudents.length} students in{" "}
                {
                  sortedPeriods.find(
                    (p) => p.filename === selectedPeriod,
                  )?.period_name
                }
              </p>
            )}
          </div>
        )}

        {/* Student Filter */}
        <div
          data-tutorial="grade-student-filter"
          style={{
            padding: "15px",
            background:
              "linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(124, 58, 237, 0.05))",
            borderRadius: "12px",
            border: "1px solid rgba(139, 92, 246, 0.2)",
            marginBottom: "20px",
          }}
        >
          <label
            className="label"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Icon
              name="User"
              size={16}
              style={{ color: "#8b5cf6" }}
            />
            Filter by Student
          </label>
          {selectedPeriod && periodStudents.length > 0 ? (
            <select
              className="input"
              value={gradeFilterStudent}
              onChange={(e) =>
                setGradeFilterStudent(e.target.value)
              }
              style={{ cursor: "pointer" }}
            >
              <option value="">All Students in Period</option>
              {periodStudents.map((student, idx) => {
                const displayName =
                  student.full ||
                  student.name ||
                  `${student.first || ""} ${student.last || ""}`.trim() ||
                  String(student);
                return (
                  <option key={idx} value={displayName}>
                    {displayName}
                  </option>
                );
              })}
            </select>
          ) : (
            <div style={{ position: "relative" }}>
              <input
                type="text"
                className="input"
                list="grade-student-suggestions"
                value={gradeFilterStudent}
                onChange={(e) =>
                  setGradeFilterStudent(e.target.value)
                }
                onClick={(e) => {
                  if (gradeFilterStudent) {
                    e.target.dataset.prev = gradeFilterStudent;
                    setGradeFilterStudent("");
                  }
                }}
                onBlur={(e) => {
                  if (
                    !gradeFilterStudent &&
                    e.target.dataset.prev
                  ) {
                    setGradeFilterStudent(e.target.dataset.prev);
                    e.target.dataset.prev = "";
                  }
                }}
                placeholder={
                  sortedPeriods.length > 0
                    ? "Type or select student..."
                    : "Type student name to filter..."
                }
                style={{
                  fontSize: "0.9rem",
                  paddingRight: gradeFilterStudent
                    ? "30px"
                    : undefined,
                }}
              />
              {gradeFilterStudent && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setGradeFilterStudent("");
                  }}
                  style={{
                    position: "absolute",
                    right: "8px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#888",
                    padding: "4px",
                    display: "flex",
                    alignItems: "center",
                  }}
                  title="Clear"
                >
                  <Icon name="X" size={14} />
                </button>
              )}
              <datalist id="grade-student-suggestions">
                {sortedPeriods
                  .flatMap((p) => p.students || [])
                  .map((s, i) => {
                    const name =
                      s.full ||
                      s.name ||
                      (
                        (s.first || "") +
                        " " +
                        (s.last || "")
                      ).trim();
                    return <option key={i} value={name} />;
                  })}
              </datalist>
            </div>
          )}
          {gradeFilterStudent && (
            <p
              style={{
                fontSize: "0.75rem",
                color: "#8b5cf6",
                marginTop: "8px",
                fontWeight: 500,
              }}
            >
              ✓ Will only grade files for "{gradeFilterStudent}"
            </p>
          )}
        </div>

        {/* Assignment Filter */}
        {savedAssignments.length > 0 && (
          <div
            data-tutorial="grade-assignment-filter"
            style={{
              padding: "15px",
              background:
                "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
              borderRadius: "12px",
              border: "1px solid rgba(16, 185, 129, 0.2)",
              marginBottom: "20px",
            }}
          >
            <label
              className="label"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Icon
                name="FileText"
                size={16}
                style={{ color: "#10b981" }}
              />
              Filter by Assignment
            </label>
            <select
              className="input"
              value={gradeFilterAssignment}
              onChange={async (e) => {
                const assignmentName = e.target.value;
                setGradeFilterAssignment(assignmentName);
                // Auto-load the assignment config when selected
                if (assignmentName) {
                  try {
                    const data =
                      await api.loadAssignment(assignmentName);
                    if (data.assignment) {
                      setGradeAssignment({
                        ...data.assignment,
                        title: data.assignment.title || "",
                        customMarkers:
                          data.assignment.customMarkers || [],
                        gradingNotes:
                          data.assignment.gradingNotes || "",
                        responseSections:
                          data.assignment.responseSections || [],
                        excludeMarkers:
                          data.assignment.excludeMarkers || [],
                      });
                      if (data.assignment.importedDoc) {
                        setGradeImportedDoc(
                          data.assignment.importedDoc,
                        );
                      }
                      addToast(
                        `Loaded "${assignmentName}"`,
                        "success",
                      );
                    }
                  } catch (err) {
                    console.error("Load error:", err);
                  }
                }
              }}
              style={{ cursor: "pointer" }}
            >
              <option value="">Select Assignment...</option>
              {savedAssignments.map((name) => (
                <option key={name} value={name}>
                  {name}
                  {savedAssignmentData[name]?.completionOnly
                    ? " (Completion)"
                    : ""}
                </option>
              ))}
            </select>
            {gradeFilterAssignment && (
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "#10b981",
                  marginTop: "8px",
                  fontWeight: 500,
                }}
              >
                ✓ Using "{gradeFilterAssignment}" configuration
              </p>
            )}
          </div>
        )}

        {/* Active Filters Summary */}
        {(gradeFilterStudent || gradeFilterAssignment) && (
          <div
            style={{
              padding: "12px 15px",
              background: "rgba(251, 191, 36, 0.1)",
              borderRadius: "10px",
              border: "1px solid rgba(251, 191, 36, 0.3)",
              marginBottom: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
              }}
            >
              <Icon
                name="Filter"
                size={16}
                style={{ color: "#f59e0b" }}
              />
              <span
                style={{
                  fontSize: "0.85rem",
                  color: "#f59e0b",
                  fontWeight: 600,
                }}
              >
                Active Filters:
              </span>
              {gradeFilterStudent && (
                <span
                  style={{
                    padding: "4px 10px",
                    background: "rgba(99, 102, 241, 0.2)",
                    borderRadius: "6px",
                    fontSize: "0.8rem",
                    color: "var(--accent-primary)",
                  }}
                >
                  Student: {gradeFilterStudent}
                </span>
              )}
              {gradeFilterAssignment && (
                <span
                  style={{
                    padding: "4px 10px",
                    background: "rgba(16, 185, 129, 0.2)",
                    borderRadius: "6px",
                    fontSize: "0.8rem",
                    color: "#10b981",
                  }}
                >
                  Assignment: {gradeFilterAssignment}
                </span>
              )}
            </div>
            <button
              onClick={() => {
                setGradeFilterStudent("");
                setGradeFilterAssignment("");
              }}
              style={{
                padding: "4px 10px",
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                borderRadius: "6px",
                color: "#ef4444",
                fontSize: "0.8rem",
                cursor: "pointer",
              }}
            >
              Clear Filters
            </button>
          </div>
        )}

        {/* Matching Files Preview - Show when student filter is set */}
        {gradeFilterStudent && availableFiles.length > 0 && (
          <div
            style={{
              padding: "15px",
              background:
                "linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(37, 99, 235, 0.05))",
              borderRadius: "12px",
              border: "1px solid rgba(59, 130, 246, 0.2)",
              marginBottom: "20px",
            }}
          >
            <label
              className="label"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "10px",
              }}
            >
              <Icon
                name="FileSearch"
                size={16}
                style={{ color: "#3b82f6" }}
              />
              Matching Submissions for "{gradeFilterStudent}"
            </label>
            {(() => {
              let studentName = gradeFilterStudent.toLowerCase();
              // Handle "Last; First" or "Last, First" roster format
              if (studentName.includes(';') || studentName.includes(',')) {
                const parts = studentName.split(/[;,]/).map(p => p.trim());
                if (parts.length >= 2) {
                  const lastName = parts[0];
                  const firstName = parts[1].split(' ')[0];
                  studentName = firstName + ' ' + lastName;
                }
              }
              const matchingFiles = availableFiles.filter((f) => {
                const fileName = f.name.toLowerCase();
                return (
                  fileName.includes(
                    studentName.replace(/\s+/g, ""),
                  ) ||
                  fileName.includes(
                    studentName.replace(/\s+/g, "_"),
                  ) ||
                  fileName.includes(
                    studentName.replace(/\s+/g, "-"),
                  ) ||
                  fileName.includes(studentName)
                );
              });

              if (matchingFiles.length === 0) {
                return (
                  <p
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-muted)",
                      margin: 0,
                    }}
                  >
                    No files found matching "{gradeFilterStudent}"
                  </p>
                );
              }

              return (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "#3b82f6",
                      margin: "0 0 5px 0",
                    }}
                  >
                    {matchingFiles.length} file
                    {matchingFiles.length !== 1 ? "s" : ""} found -
                    select to grade:
                  </p>
                  {matchingFiles.map((file, idx) => (
                    <label
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "10px 12px",
                        background: selectedFiles.includes(
                          file.name,
                        )
                          ? "rgba(59, 130, 246, 0.2)"
                          : "var(--input-bg)",
                        borderRadius: "8px",
                        border: selectedFiles.includes(file.name)
                          ? "1px solid rgba(59, 130, 246, 0.4)"
                          : "1px solid var(--glass-border)",
                        cursor: "pointer",
                        transition: "all 0.2s",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.includes(file.name)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedFiles([
                              ...selectedFiles,
                              file.name,
                            ]);
                          } else {
                            setSelectedFiles(
                              selectedFiles.filter(
                                (f) => f !== file.name,
                              ),
                            );
                          }
                        }}
                        style={{
                          width: "16px",
                          height: "16px",
                          cursor: "pointer",
                        }}
                      />
                      <div style={{ flex: 1 }}>
                        <span
                          style={{
                            fontSize: "0.9rem",
                            fontWeight: 500,
                          }}
                        >
                          {file.name}
                        </span>
                        {file.graded && (
                          <span
                            style={{
                              marginLeft: "8px",
                              padding: "2px 6px",
                              background: "rgba(16, 185, 129, 0.2)",
                              borderRadius: "4px",
                              fontSize: "0.7rem",
                              color: "#10b981",
                            }}
                          >
                            Already Graded
                          </span>
                        )}
                      </div>
                    </label>
                  ))}
                  {selectedFiles.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        marginTop: "5px",
                      }}
                    >
                      <button
                        onClick={() =>
                          setSelectedFiles(
                            matchingFiles.map((f) => f.name),
                          )
                        }
                        style={{
                          padding: "6px 12px",
                          background: "rgba(59, 130, 246, 0.1)",
                          border:
                            "1px solid rgba(59, 130, 246, 0.3)",
                          borderRadius: "6px",
                          color: "#3b82f6",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                        }}
                      >
                        Select All
                      </button>
                      <button
                        onClick={() => setSelectedFiles([])}
                        style={{
                          padding: "6px 12px",
                          background: "rgba(239, 68, 68, 0.1)",
                          border:
                            "1px solid rgba(239, 68, 68, 0.3)",
                          borderRadius: "6px",
                          color: "#ef4444",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                        }}
                      >
                        Clear Selection
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* Skip Verified Toggle - Show when there are unverified results */}
        {status.results &&
          status.results.some(
            (r) => r.marker_status === "unverified",
          ) && (
            <div
              style={{
                padding: "15px",
                background:
                  "linear-gradient(135deg, rgba(251, 191, 36, 0.1), rgba(245, 158, 11, 0.05))",
                borderRadius: "12px",
                border: "1px solid rgba(251, 191, 36, 0.3)",
                marginBottom: "20px",
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={skipVerified}
                  onChange={(e) =>
                    setSkipVerified(e.target.checked)
                  }
                  style={{
                    width: "18px",
                    height: "18px",
                    cursor: "pointer",
                  }}
                />
                <div>
                  <span
                    style={{ fontWeight: 600, color: "#fbbf24" }}
                  >
                    Regrade All (Including Verified)
                  </span>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      margin: "4px 0 0 0",
                    }}
                  >
                    {`Check to also regrade ${status.results.filter((r) => r.marker_status === "verified").length} verified grades. ${status.results.filter((r) => r.marker_status === "unverified").length} unverified will always be regraded.`}
                  </p>
                </div>
              </label>
            </div>
          )}

        {/* Exclude students already graded in this session */}
        {status.results.length > 0 && (
          <div
            className="glass-card"
            style={{
              padding: "15px 20px",
              marginBottom: "20px",
              background: "rgba(34, 197, 94, 0.05)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={excludeGradedStudents}
                onChange={(e) =>
                  setExcludeGradedStudents(e.target.checked)
                }
                style={{
                  width: "18px",
                  height: "18px",
                  cursor: "pointer",
                }}
              />
              <div>
                <span
                  style={{ fontWeight: 600, color: "#22c55e" }}
                >
                  Exclude Already Graded Files
                </span>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    margin: "4px 0 0 0",
                  }}
                >
                  Skip {(() => {
                    // Filter results by current assignment filter
                    let relevantResults = status.results;
                    if (gradeFilterAssignment) {
                      const cfg = savedAssignmentData[gradeFilterAssignment] || {};
                      const importedFn = (cfg.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                      const names = [gradeFilterAssignment, cfg.title || "", ...(cfg.aliases || []), importedFn].filter(Boolean).map(n => n.toLowerCase());
                      relevantResults = status.results.filter((r) => {
                        const rAssign = (r.assignment || "").toLowerCase();
                        const rFile = (r.filename || "").toLowerCase();
                        return names.some(n => rAssign.includes(n) || rFile.includes(n) || n.includes(rAssign));
                      });
                    }
                    return relevantResults.length;
                  })()} file(s) already graded{gradeFilterAssignment ? ` for "${gradeFilterAssignment}"` : ""}.
                  Only grade new files.
                </p>
              </div>
            </label>
          </div>
        )}

        {/* Exclude students already approved */}
        {status.results.length > 0 && Object.values(emailApprovals).some((v) => v === "approved") && (
          <div
            className="glass-card"
            style={{
              padding: "15px 20px",
              marginBottom: "20px",
              background: "rgba(34, 197, 94, 0.05)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={excludeApprovedStudents}
                onChange={(e) =>
                  setExcludeApprovedStudents(e.target.checked)
                }
                style={{
                  width: "18px",
                  height: "18px",
                  cursor: "pointer",
                }}
              />
              <div>
                <span
                  style={{ fontWeight: 600, color: "#22c55e" }}
                >
                  Exclude Already Approved
                </span>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    margin: "4px 0 0 0",
                  }}
                >
                  Skip {(() => {
                    // Count approved results, optionally filtered by assignment
                    let count = 0;
                    if (gradeFilterAssignment) {
                      const cfg = savedAssignmentData[gradeFilterAssignment] || {};
                      const importedFn = (cfg.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                      const names = [gradeFilterAssignment, cfg.title || "", ...(cfg.aliases || []), importedFn].filter(Boolean).map(n => n.toLowerCase());
                      status.results.forEach((r, idx) => {
                        if (emailApprovals[idx] !== "approved") return;
                        const rAssign = (r.assignment || "").toLowerCase();
                        const rFile = (r.filename || "").toLowerCase();
                        if (names.some(n => rAssign.includes(n) || rFile.includes(n) || n.includes(rAssign))) {
                          count++;
                        }
                      });
                    } else {
                      status.results.forEach((r, idx) => {
                        if (emailApprovals[idx] === "approved") count++;
                      });
                    }
                    return count;
                  })()} approved file(s){gradeFilterAssignment ? ` for "${gradeFilterAssignment}"` : ""}.
                  Only re-grade unapproved files.
                </p>
              </div>
            </label>
          </div>
        )}

        {/* Grading Notes removed from Grade tab — use Grading Setup (Builder) instead */}

        {/* Individual Upload - For Paper/Handwritten Assignments */}
        <div
          data-tutorial="grade-individual"
          style={{
            marginTop: "20px",
            padding: "20px",
            borderRadius: "16px",
            background:
              "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
            border: "1px solid rgba(16, 185, 129, 0.2)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "15px",
            }}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "rgba(16, 185, 129, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon
                name="Camera"
                size={20}
                style={{ color: "#10b981" }}
              />
            </div>
            <div>
              <h4 style={{ margin: 0, fontWeight: 600 }}>
                Individual Upload
              </h4>
              <p
                style={{
                  margin: 0,
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                }}
              >
                For paper/handwritten assignments (uses GPT-4o
                vision)
              </p>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: individualUpload.preview
                ? "1fr 1fr"
                : "1fr",
              gap: "15px",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              {/* Student Name with Autocomplete */}
              <div style={{ position: "relative" }}>
                <input
                  type="text"
                  className="input"
                  placeholder={
                    periodStudents.length > 0
                      ? "Start typing student name..."
                      : "Student name..."
                  }
                  value={individualUpload.studentName}
                  onChange={(e) =>
                    setIndividualUpload((prev) => ({
                      ...prev,
                      studentName: e.target.value,
                      studentInfo: null, // Clear selected student when typing
                      showSuggestions: e.target.value.length >= 2,
                    }))
                  }
                  onFocus={() =>
                    setIndividualUpload((prev) => ({
                      ...prev,
                      showSuggestions: prev.studentName.length >= 2,
                    }))
                  }
                  onBlur={() =>
                    setTimeout(
                      () =>
                        setIndividualUpload((prev) => ({
                          ...prev,
                          showSuggestions: false,
                        })),
                      200,
                    )
                  }
                />
                {/* Autocomplete Dropdown */}
                {individualUpload.showSuggestions &&
                  getStudentSuggestions(
                    individualUpload.studentName,
                  ).length > 0 && (
                    <div
                      style={{
                        position: "absolute",
                        top: "100%",
                        left: 0,
                        right: 0,
                        background: "var(--card-bg)",
                        border: "1px solid var(--glass-border)",
                        borderRadius: "8px",
                        marginTop: "4px",
                        zIndex: 100,
                        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                        maxHeight: "200px",
                        overflowY: "auto",
                      }}
                    >
                      {getStudentSuggestions(
                        individualUpload.studentName,
                      ).map((student, idx) => (
                        <div
                          key={idx}
                          onClick={() =>
                            setIndividualUpload((prev) => ({
                              ...prev,
                              studentName:
                                student.full ||
                                `${student.first} ${student.last}`,
                              studentInfo: student,
                              showSuggestions: false,
                            }))
                          }
                          style={{
                            padding: "10px 12px",
                            cursor: "pointer",
                            borderBottom:
                              idx <
                              getStudentSuggestions(
                                individualUpload.studentName,
                              ).length -
                                1
                                ? "1px solid var(--glass-border)"
                                : "none",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                          onMouseEnter={(e) =>
                            (e.target.style.background =
                              "var(--glass-bg)")
                          }
                          onMouseLeave={(e) =>
                            (e.target.style.background =
                              "transparent")
                          }
                        >
                          <Icon
                            name="User"
                            size={16}
                            style={{ color: "var(--text-muted)" }}
                          />
                          <div>
                            <div style={{ fontWeight: 500 }}>
                              {student.full ||
                                `${student.first} ${student.last}`}
                            </div>
                            {student.email && (
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-muted)",
                                }}
                              >
                                {student.email}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                {/* Selected Student Indicator */}
                {individualUpload.studentInfo && (
                  <div
                    style={{
                      marginTop: "6px",
                      fontSize: "0.75rem",
                      color: "#10b981",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <Icon name="CheckCircle" size={12} />
                    Student matched from roster
                  </div>
                )}
              </div>

              <div
                onClick={() =>
                  document
                    .getElementById("individualFileInput")
                    ?.click()
                }
                style={{
                  padding: "20px",
                  border: "2px dashed var(--glass-border)",
                  borderRadius: "10px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: individualUpload.file
                    ? "rgba(16, 185, 129, 0.1)"
                    : "var(--glass-bg)",
                }}
              >
                <input
                  id="individualFileInput"
                  type="file"
                  accept="image/*,.pdf,.heic,.heif"
                  onChange={handleIndividualFileSelect}
                  style={{ display: "none" }}
                />
                {individualUpload.file ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={20}
                      style={{ color: "#10b981" }}
                    />
                    <span
                      style={{
                        fontWeight: 500,
                        fontSize: "0.9rem",
                      }}
                    >
                      {individualUpload.file.name}
                    </span>
                  </div>
                ) : (
                  <>
                    <Icon
                      name="Upload"
                      size={24}
                      style={{ color: "var(--text-muted)" }}
                    />
                    <p
                      style={{
                        margin: "8px 0 0",
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                      }}
                    >
                      Click to upload image
                    </p>
                  </>
                )}
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={handleIndividualGrade}
                  disabled={
                    !individualUpload.file ||
                    !individualUpload.studentName.trim() ||
                    individualUpload.isGrading
                  }
                  className="btn btn-primary"
                  style={{
                    flex: 1,
                    opacity:
                      !individualUpload.file ||
                      !individualUpload.studentName.trim() ||
                      individualUpload.isGrading
                        ? 0.5
                        : 1,
                  }}
                >
                  {individualUpload.isGrading ? (
                    <>Grading...</>
                  ) : (
                    <>
                      <Icon name="Sparkles" size={16} />
                      Grade
                    </>
                  )}
                </button>
                {individualUpload.file && (
                  <button
                    onClick={clearIndividualUpload}
                    className="btn btn-secondary"
                    style={{ padding: "8px 12px" }}
                  >
                    <Icon name="X" size={16} />
                  </button>
                )}
              </div>

              {individualUpload.result && (
                <div
                  style={{
                    padding: "12px",
                    borderRadius: "10px",
                    background: "rgba(16, 185, 129, 0.15)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "1.5rem",
                        fontWeight: 800,
                        color: "#10b981",
                      }}
                    >
                      {individualUpload.result.letter_grade}
                    </span>
                    <div>
                      <div style={{ fontWeight: 600 }}>
                        {individualUpload.result.score}%
                      </div>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        {individualUpload.studentName}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {individualUpload.preview && (
              <div
                style={{
                  borderRadius: "10px",
                  overflow: "hidden",
                  border: "1px solid var(--glass-border)",
                }}
              >
                <img
                  src={individualUpload.preview}
                  alt="Preview"
                  style={{
                    width: "100%",
                    height: "auto",
                    maxHeight: "250px",
                    objectFit: "contain",
                    background: "#fff",
                  }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Progress */}
        {status.is_running && (
          <div style={{ marginTop: "20px" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "8px",
                fontSize: "0.9rem",
              }}
            >
              <span>Progress</span>
              <span>
                {status.progress}/{status.total}
              </span>
            </div>
            <div
              style={{
                height: "8px",
                background: "var(--btn-secondary-bg)",
                borderRadius: "4px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${pct}%`,
                  background:
                    "linear-gradient(90deg, #6366f1, #8b5cf6)",
                  transition: "width 0.3s",
                }}
              />
            </div>
            {status.current_file && (
              <p
                style={{
                  marginTop: "8px",
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                }}
              >
                {status.current_file}
              </p>
            )}
            {status.session_cost && status.session_cost.total_cost > 0 && (
              <div style={{
                display: "flex", gap: "16px", fontSize: "0.8rem",
                color: "var(--text-secondary)", marginTop: "8px"
              }}>
                <span>Cost: ${status.session_cost.total_cost.toFixed(4)}</span>
                <span>Tokens: {(status.session_cost.total_input_tokens + status.session_cost.total_output_tokens).toLocaleString()}</span>
                <span>API Calls: {status.session_cost.total_api_calls}</span>
              </div>
            )}
          </div>
        )}

        {/* Pre-grading cost estimate */}
        {!status.is_running && selectedFiles.length > 0 && (
          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "8px" }}>
            Estimated cost: ${(selectedFiles.length * (MODEL_COST_PER_ASSIGNMENT[config.ai_model] || 0.001)).toFixed(4)}
            {" "}for {selectedFiles.length} file{selectedFiles.length !== 1 ? "s" : ""} with {config.ai_model}
            {config.cost_limit_per_session > 0 && (
              <span> (limit: ${config.cost_limit_per_session.toFixed(2)})</span>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
