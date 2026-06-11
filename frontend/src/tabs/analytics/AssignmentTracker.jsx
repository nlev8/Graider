import React, { useState, useEffect } from "react";
import Icon from "../../components/Icon";

// Assignment Tracker (missing/submitted work) — moved verbatim from the
// StaticSections component in AnalyticsTab.jsx (CQ wave 1 split). The
// tracker-local state (filters, view mode, expanded periods) moved with it;
// rendered output is unchanged.

// Student-filtered report — verbatim from the `if (missingStudentFilter)` branch.
function StudentMissingReport({
  missingStudentFilter, periodsToCheck, periodStudentMap,
  assignmentsToCheck, hasUploaded,
}) {
  const studentLower =
    missingStudentFilter.toLowerCase();
  let studentInfo = null;
  let studentPeriod = null;

  for (const period of periodsToCheck) {
    const found = (periodStudentMap[period.period_name] || period.students || []).find(
      (s) => {
        const fullName = (
          s.full ||
          s.name ||
          (
            (s.first || "") +
            " " +
            (s.last || "")
          ).trim()
        ).toLowerCase();
        return (
          fullName.includes(studentLower) ||
          studentLower.includes(fullName)
        );
      },
    );
    if (found) {
      studentInfo = found;
      studentPeriod = period.period_name;
      break;
    }
  }

  const displayName = studentInfo
    ? studentInfo.full ||
      studentInfo.name ||
      (
        (studentInfo.first || "") +
        " " +
        (studentInfo.last || "")
      ).trim()
    : missingStudentFilter;

  const missing = assignmentsToCheck.filter(
    (a) => !hasUploaded(displayName, a),
  );
  const submitted = assignmentsToCheck.filter((a) =>
    hasUploaded(displayName, a),
  );

  return (
    <div>
      <div
        style={{
          padding: "15px",
          background: "rgba(0,0,0,0.2)",
          borderRadius: "8px",
          marginBottom: "15px",
        }}
      >
        <div
          style={{
            fontWeight: 600,
            marginBottom: "8px",
          }}
        >
          {displayName}{" "}
          {studentPeriod && (
            <span
              style={{
                color: "#888",
                fontWeight: 400,
              }}
            >
              ({studentPeriod})
            </span>
          )}
        </div>
        <div
          style={{
            display: "flex",
            gap: "20px",
            fontSize: "0.9rem",
          }}
        >
          <span>
            <span
              style={{
                color: "#f59e0b",
                fontWeight: 600,
              }}
            >
              {missing.length}
            </span>{" "}
            missing
          </span>
          <span>
            <span
              style={{
                color: "#10b981",
                fontWeight: 600,
              }}
            >
              {submitted.length}
            </span>{" "}
            uploaded
          </span>
          <span>
            <span
              style={{
                color: "#6366f1",
                fontWeight: 600,
              }}
            >
              {assignmentsToCheck.length}
            </span>{" "}
            total
          </span>
        </div>
      </div>
      {missing.length > 0 ? (
        <div>
          <div
            style={{
              fontSize: "0.85rem",
              color: "#888",
              marginBottom: "10px",
            }}
          >
            Missing:
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            {missing.map((a) => (
              <span
                key={a}
                style={{
                  padding: "6px 12px",
                  background:
                    "rgba(251,191,36,0.15)",
                  borderRadius: "6px",
                  fontSize: "0.85rem",
                  color: "#b45309",
                  border: "1px solid rgba(180,83,9,0.3)",
                }}
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div
          style={{
            color: "#10b981",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <Icon name="CheckCircle" size={18} />
          All assignments uploaded!
        </div>
      )}
    </div>
  );
}

// By-period report — verbatim from the default branch of the report IIFE.
function PeriodMissingReport({
  periodsToCheck, periodStudentMap, assignmentsToCheck, hasUploaded,
  assignmentViewMode, missingPeriodFilter, expandedPeriods, setExpandedPeriods,
}) {
  // Default: show by period
  let totalMissing = 0;
  let totalStudents = 0;
  const periodReports = [];

  periodsToCheck.forEach((period) => {
    const students = periodStudentMap[period.period_name] || period.students || [];
    totalStudents += students.length;
    const studentsWithMissing = [];

    const showSubmitted = assignmentViewMode === "submitted";
    students.forEach((student) => {
      const name =
        student.full ||
        student.name ||
        (
          (student.first || "") +
          " " +
          (student.last || "")
        ).trim();
      const missing = [];
      const submitted = [];
      assignmentsToCheck.forEach((a) => {
        if (hasUploaded(name, a)) {
          submitted.push(a);
        } else {
          missing.push(a);
        }
      });
      if (missing.length > 0) {
        studentsWithMissing.push({ name, missing, submitted });
        totalMissing += missing.length;
      } else if (showSubmitted) {
        studentsWithMissing.push({ name, missing: [], submitted });
      }
    });

    const studentsWithSubmitted = studentsWithMissing.filter(s => s.submitted.length > 0);
    const studentsActuallyMissing = studentsWithMissing.filter(s => s.missing.length > 0);

    periodReports.push({
      period: period.period_name,
      total: students.length,
      studentsWithMissing: studentsActuallyMissing,
      studentsWithSubmitted,
      allComplete: studentsActuallyMissing.length === 0,
    });
  });

  const totalSlots =
    totalStudents * assignmentsToCheck.length;
  const totalUploaded = totalSlots - totalMissing;

  return (
    <div>
      {/* Summary Stats */}
      <div
        style={{
          display: "flex",
          gap: "20px",
          marginBottom: "20px",
          padding: "15px",
          background: "rgba(0,0,0,0.2)",
          borderRadius: "8px",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "1.8rem",
              fontWeight: 700,
              color: "#f59e0b",
            }}
          >
            {totalMissing}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#888",
            }}
          >
            Missing
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "1.8rem",
              fontWeight: 700,
              color: "#10b981",
            }}
          >
            {totalUploaded}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#888",
            }}
          >
            Uploaded
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "1.8rem",
              fontWeight: 700,
              color: "#6366f1",
            }}
          >
            {totalStudents}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#888",
            }}
          >
            Students
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "1.8rem",
              fontWeight: 700,
              color: "#8b5cf6",
            }}
          >
            {assignmentsToCheck.length}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#888",
            }}
          >
            Assignments
          </div>
        </div>
      </div>

      {/* Per Period Breakdown */}
      <div style={{ display: "grid", gap: "12px" }}>
        {periodReports.map((report) => {
          const canCollapse = !missingPeriodFilter && periodReports.length > 1;
          const isCollapsed = canCollapse && !expandedPeriods.has(report.period);
          const displayStudents = assignmentViewMode === "submitted"
            ? report.studentsWithSubmitted
            : report.studentsWithMissing;
          const isMissing = assignmentViewMode === "missing";
          return (
          <div
            key={report.period}
            style={{
              padding: "12px 15px",
              background: "rgba(0,0,0,0.15)",
              borderRadius: "8px",
              border: isMissing
                ? (report.allComplete ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(251,191,36,0.3)")
                : "1px solid rgba(16,185,129,0.3)",
            }}
          >
            <div
              onClick={canCollapse ? () => {
                setExpandedPeriods(prev => {
                  const next = new Set(prev);
                  if (next.has(report.period)) next.delete(report.period);
                  else next.add(report.period);
                  return next;
                });
              } : undefined}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: canCollapse ? "pointer" : "default",
                marginBottom:
                  !isCollapsed && displayStudents.length > 0
                    ? "10px"
                    : 0,
              }}
            >
              <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                {canCollapse && (
                  <Icon name={isCollapsed ? "ChevronRight" : "ChevronDown"} size={16} style={{ opacity: 0.6 }} />
                )}
                {report.period}
              </span>
              <span style={{ fontSize: "0.85rem" }}>
                {isMissing ? (
                  report.allComplete ? (
                    <span style={{ color: "#10b981" }}>
                      ✓ All complete
                    </span>
                  ) : (
                    <span style={{ color: "#b45309" }}>
                      {report.studentsWithMissing.length}{" "}
                      students missing work
                    </span>
                  )
                ) : (
                  <span style={{ color: "#059669" }}>
                    {report.studentsWithSubmitted.length} students with submissions
                  </span>
                )}
              </span>
            </div>
            {!isCollapsed && displayStudents.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                {displayStudents.map(
                  (s, idx) => {
                    const items = isMissing ? s.missing : s.submitted;
                    return (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        flexWrap: "wrap",
                      }}
                    >
                      <span
                        style={{
                          minWidth: "140px",
                          fontWeight: 500,
                          fontSize: "0.9rem",
                        }}
                      >
                        {s.name}
                        {!isMissing && s.missing.length > 0 && (
                          <span style={{ color: "#b45309", fontWeight: 400, fontSize: "0.75rem", marginLeft: "6px" }}>
                            ({s.missing.length} missing)
                          </span>
                        )}
                      </span>
                      <div
                        style={{
                          display: "flex",
                          gap: "5px",
                          flexWrap: "wrap",
                        }}
                      >
                        {items.map((a) => (
                          <span
                            key={a}
                            style={{
                              padding: "2px 8px",
                              background: isMissing
                                ? "rgba(251,191,36,0.15)"
                                : "rgba(16,185,129,0.15)",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              color: isMissing ? "#b45309" : "#059669",
                              border: isMissing
                                ? "1px solid rgba(180,83,9,0.3)"
                                : "1px solid rgba(16,185,129,0.3)",
                            }}
                          >
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                    );
                  },
                )}
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

// Report computation — verbatim from the report IIFE preamble.
function MissingWorkReport({
  missingAssignmentFilter, missingPeriodFilter, missingStudentFilter,
  assignmentViewMode, expandedPeriods, setExpandedPeriods,
  savedAssignments, savedAssignmentData, sortedPeriods, periodStudentMap,
  missingUploadedFiles,
}) {
  // Get assignments to check
  const assignmentsToCheck = missingAssignmentFilter
    ? [missingAssignmentFilter]
    : savedAssignments;

  // Get periods to check
  const periodsToCheck = missingPeriodFilter
    ? sortedPeriods.filter(
        (p) => p.filename === missingPeriodFilter,
      )
    : sortedPeriods;

  // Pre-normalize uploaded file names once (not per call)
  const uploadedNormed = missingUploadedFiles.map((f) => {
    let name = (f.name || f)
      .toLowerCase()
      .replace(/\.(docx|pdf|doc|txt)$/i, "");
    name = name.replace(/\s*\(\d+\)\s*$/, "");
    name = name.replace(/\s*-\s*copy\s*\d*$/i, "");
    return name
      .replace(/[^\w\s&']/g, " ")
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  });

  // Pre-normalize assignment names once
  const assignmentNormed = {};
  assignmentsToCheck.forEach((assignmentName) => {
    const assignmentData = savedAssignmentData[assignmentName] || {};
    assignmentNormed[assignmentName] = [
      assignmentName.toLowerCase(),
      ...(assignmentData.aliases || []).map((a) => a.toLowerCase()),
      ...(assignmentData.importedFilename ? [assignmentData.importedFilename.replace(/\.\w+$/, "").toLowerCase()] : []),
    ].map((aName) => {
      const normName = aName.replace(/[^\w\s&']/g, " ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
      const words = normName.split(" ").filter((w) => w.length > 3);
      return { normName, words };
    });
  });

  // Cache results: "studentName|assignmentName" -> boolean
  const uploadCache = {};
  const hasUploaded = (studentName, assignmentName) => {
    const key = studentName + "|" + assignmentName;
    if (key in uploadCache) return uploadCache[key];

    const sName = studentName.toLowerCase();
    const sNorm = sName.replace(/[_\-\.,;]/g, " ").replace(/\s+/g, " ").trim();
    const nameParts = sNorm.split(" ");
    const nameThreshold = Math.max(2, nameParts.length - 1);
    const sJoined = sNorm.replace(/ /g, "");
    const normChecks = assignmentNormed[assignmentName] || [];

    const result = uploadedNormed.some((fNorm) => {
      const nameMatchCount = nameParts.filter((part) => fNorm.includes(part)).length;
      const hasStudentName = nameMatchCount >= nameThreshold || fNorm.includes(sJoined);
      if (!hasStudentName) return false;
      return normChecks.some(({ normName, words }) => {
        if (fNorm.includes(normName)) return true;
        if (normName.length > 15 && fNorm.includes(normName.slice(0, Math.min(normName.length, 35)))) return true;
        if (words.length < 2) return false;
        const matched = words.filter((w) => fNorm.includes(w)).length;
        return matched >= Math.max(3, Math.ceil(words.length * 0.75));
      });
    });
    uploadCache[key] = result;
    return result;
  };

  // If filtering by student
  if (missingStudentFilter) {
    return (
      <StudentMissingReport
        missingStudentFilter={missingStudentFilter}
        periodsToCheck={periodsToCheck}
        periodStudentMap={periodStudentMap}
        assignmentsToCheck={assignmentsToCheck}
        hasUploaded={hasUploaded}
      />
    );
  }

  // Default: show by period
  return (
    <PeriodMissingReport
      periodsToCheck={periodsToCheck}
      periodStudentMap={periodStudentMap}
      assignmentsToCheck={assignmentsToCheck}
      hasUploaded={hasUploaded}
      assignmentViewMode={assignmentViewMode}
      missingPeriodFilter={missingPeriodFilter}
      expandedPeriods={expandedPeriods}
      setExpandedPeriods={setExpandedPeriods}
    />
  );
}

// Assignment Tracker card — owns the tracker-local state that previously
// lived in StaticSections (it was used nowhere else there).
function AssignmentTrackerCard({
  periodStudentMap, sortedPeriods, savedAssignments, savedAssignmentData,
  addToast, periods,
}) {
  const [missingAssignmentFilter, setMissingAssignmentFilter] = useState("");
  const [missingPeriodFilter, setMissingPeriodFilter] = useState("");
  const [expandedPeriods, setExpandedPeriods] = useState(new Set());
  const [missingStudentFilter, setMissingStudentFilter] = useState("");
  const [assignmentViewMode, setAssignmentViewMode] = useState("missing"); // "missing" | "submitted"
  const [missingUploadedFiles, setMissingUploadedFiles] = useState([]);
  const [missingFilesLoading, setMissingFilesLoading] = useState(false);

  // listFiles removed (portal-only workflow) — no local folder to scan
  useEffect(() => {
    setMissingUploadedFiles([]);
  }, []);

  return (
    <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "10px",
              margin: 0,
            }}
          >
            <Icon name={assignmentViewMode === "missing" ? "UserX" : "CheckSquare"} size={20} />
            Assignment Tracker
          </h3>
          <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
            <button
              onClick={() => setAssignmentViewMode("missing")}
              style={{
                padding: "4px 12px",
                fontSize: "0.8rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: assignmentViewMode === "missing" ? "rgba(251,191,36,0.3)" : "transparent",
                color: assignmentViewMode === "missing" ? "#b45309" : "var(--text-secondary)",
              }}
            >
              Missing
            </button>
            <button
              onClick={() => setAssignmentViewMode("submitted")}
              style={{
                padding: "4px 12px",
                fontSize: "0.8rem",
                fontWeight: 600,
                border: "none",
                borderLeft: "1px solid var(--glass-border)",
                cursor: "pointer",
                background: assignmentViewMode === "submitted" ? "rgba(16,185,129,0.3)" : "transparent",
                color: assignmentViewMode === "submitted" ? "#059669" : "var(--text-secondary)",
              }}
            >
              Submitted
            </button>
          </div>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => {
            addToast("File scanning not available in portal mode", "info");
          }}
          style={{ padding: "6px 12px", fontSize: "0.85rem" }}
        >
          <Icon name="RefreshCw" size={14} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div
        style={{
          display: "flex",
          gap: "15px",
          flexWrap: "wrap",
          marginBottom: "20px",
        }}
      >
        <div style={{ flex: "1", minWidth: "180px" }}>
          <label
            style={{
              fontSize: "0.8rem",
              color: "#888",
              marginBottom: "4px",
              display: "block",
            }}
          >
            Period
          </label>
          <select
            className="input"
            value={missingPeriodFilter}
            onChange={(e) => {
              setMissingPeriodFilter(e.target.value);
              setMissingStudentFilter("");
            }}
            style={{ width: "100%" }}
          >
            <option value="">All Periods</option>
            {sortedPeriods.map((p) => (
              <option key={p.filename} value={p.filename}>
                {p.period_name}
              </option>
            ))}
          </select>
        </div>
        <div style={{ flex: "1", minWidth: "180px" }}>
          <label
            style={{
              fontSize: "0.8rem",
              color: "#888",
              marginBottom: "4px",
              display: "block",
            }}
          >
            Student
          </label>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              className="input"
              list="missing-student-suggestions"
              placeholder="Type or select student..."
              value={missingStudentFilter}
              onChange={(e) =>
                setMissingStudentFilter(e.target.value)
              }
              onClick={(e) => {
                if (missingStudentFilter) {
                  e.target.dataset.prev =
                    missingStudentFilter;
                  setMissingStudentFilter("");
                }
              }}
              onBlur={(e) => {
                if (
                  !missingStudentFilter &&
                  e.target.dataset.prev
                ) {
                  setMissingStudentFilter(
                    e.target.dataset.prev,
                  );
                  e.target.dataset.prev = "";
                }
              }}
              style={{
                width: "100%",
                paddingRight: missingStudentFilter
                  ? "30px"
                  : undefined,
              }}
            />
            {missingStudentFilter && (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  setMissingStudentFilter("");
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
          </div>
          <datalist id="missing-student-suggestions">
            {(missingPeriodFilter
              ? (periodStudentMap[sortedPeriods.find(
                  (p) => p.filename === missingPeriodFilter,
                )?.period_name] || [])
              : Object.values(periodStudentMap).flat()
            ).map((s, i) => {
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
        <div style={{ flex: "1", minWidth: "180px" }}>
          <label
            style={{
              fontSize: "0.8rem",
              color: "#888",
              marginBottom: "4px",
              display: "block",
            }}
          >
            Assignment
          </label>
          <select
            className="input"
            value={missingAssignmentFilter}
            onChange={(e) =>
              setMissingAssignmentFilter(e.target.value)
            }
            style={{ width: "100%" }}
          >
            <option value="">All Assignments</option>
            {savedAssignments.map((name) => (
              <option key={name} value={name}>
                {name}
                {savedAssignmentData[name]?.completionOnly
                  ? " (Completion)"
                  : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Missing Report */}
      {periods.length === 0 ? (
        <div
          style={{
            color: "#888",
            textAlign: "center",
            padding: "20px",
          }}
        >
          <Icon
            name="AlertCircle"
            size={24}
            style={{ marginBottom: "10px", opacity: 0.5 }}
          />
          <div>
            Upload period rosters in Settings to track missing
            assignments
          </div>
        </div>
      ) : missingFilesLoading ? (
        <div
          style={{
            color: "#888",
            textAlign: "center",
            padding: "20px",
          }}
        >
          Loading files...
        </div>
      ) : (
          <MissingWorkReport
            missingAssignmentFilter={missingAssignmentFilter}
            missingPeriodFilter={missingPeriodFilter}
            missingStudentFilter={missingStudentFilter}
            assignmentViewMode={assignmentViewMode}
            expandedPeriods={expandedPeriods}
            setExpandedPeriods={setExpandedPeriods}
            savedAssignments={savedAssignments}
            savedAssignmentData={savedAssignmentData}
            sortedPeriods={sortedPeriods}
            periodStudentMap={periodStudentMap}
            missingUploadedFiles={missingUploadedFiles}
          />
      )}
    </div>
  );
}

export default AssignmentTrackerCard;
