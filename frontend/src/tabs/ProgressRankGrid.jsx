import React, { useState, useEffect } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";
import StudentReportCard from "./StudentReportCard";
import RemediationDrawer from "./RemediationDrawer";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: "—" };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

export default function ProgressRankGrid({ classId }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [strugglingOnly, setStrugglingOnly] = useState(false);
  var [selectedCell, setSelectedCell] = useState(null);
  var [selectedStudent, setSelectedStudent] = useState(null);
  var [remediationTrigger, setRemediationTrigger] = useState(null);
  // shape: {standardCode, targetMode, targetStudentId?, targetStudentName?}

  function openReportCard(student) {
    setSelectedCell(null);          // close any open cell popover (z-index 9999)
    setSelectedStudent(student);    // drawer opens at z-index 9500
  }

  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassProgressRank(classId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res) {
          setError('No response from server');
          setData(null);
        } else if (res.error) {
          setError(res.error);
          setData(null);
        } else if (!res.students) {
          setError('Unexpected response format');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        var msg = e && e.message ? e.message : 'Failed to load progress rank';
        setError(msg);
        setData(null);
      })
      .finally(function() {
        if (!cancelled) setLoading(false);
      });
    return function() { cancelled = true; };
  }, [classId, attemptMode]);

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading progress rank...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--danger)" }}>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  var standards = data.standards || [];
  var students = data.students || [];

  // Filter struggling students
  var displayStudents = strugglingOnly
    ? students.filter(function(s) {
        var mastery = s.mastery || {};
        return Object.keys(mastery).some(function(code) {
          var m = mastery[code];
          return m && m.percentage != null && m.percentage < 70;
        });
      })
    : students;

  var btnStyle = function(active) {
    return {
      padding: "6px 14px",
      borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem",
      fontWeight: 600,
      cursor: "pointer",
    };
  };

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Progress Rank {String.fromCharCode(8212)} {data.class_name}
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {students.length} students {String.fromCharCode(8226)} {standards.length} standards assessed
      </p>

      {/* Controls */}
      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setStrugglingOnly(false); }} style={btnStyle(!strugglingOnly)}>All Students</button>
          <button onClick={function() { setStrugglingOnly(true); }} style={btnStyle(strugglingOnly)}>Struggling Only</button>
        </div>
      </div>

      {standards.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No standards-tagged assessments yet. Generate an assessment with standards to populate this grid.
        </p>
      ) : (
        <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "600px" }}>
            <thead>
              <tr>
                <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 2, padding: "10px 14px", textAlign: "left", fontSize: "0.8rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>
                  Student
                </th>
                {/* Compute red counts per column once. */}
                {(function() {
                  var redCounts = {};
                  standards.forEach(function(code) {
                    redCounts[code] = displayStudents.filter(function(stu) {
                      var m = stu.mastery[code];
                      return m && typeof m.percentage === "number" && m.percentage < 70;
                    }).length;
                  });
                  return standards.map(function(code) {
                    var redCount = redCounts[code];
                    return (
                      <th key={code}
                          style={{ padding: "10px 8px", fontSize: "0.7rem", fontFamily: "monospace",
                                   fontWeight: 700, borderBottom: "1px solid var(--glass-border)",
                                   borderLeft: "1px solid var(--glass-border)", minWidth: "90px",
                                   textAlign: "center", position: "relative" }}
                          className="phase4-header-cell">
                        {code}
                        {redCount > 0 && (
                          <button
                            onClick={function() {
                              setRemediationTrigger({
                                standardCode: code,
                                targetMode: "red_tier_in_class",
                              });
                            }}
                            className="phase4-header-remediate"
                            tabIndex={0}
                            aria-label={"Remediate " + redCount + " red-tier students on " + code}
                            style={{
                              position: "absolute", top: "2px", right: "2px",
                              background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                              border: "none", borderRadius: "4px", fontSize: "0.65rem",
                              padding: "2px 6px", cursor: "pointer", opacity: 0,
                              transition: "opacity 0.15s",
                            }}
                          >
                            Remediate ({redCount})
                          </button>
                        )}
                      </th>
                    );
                  });
                })()}
              </tr>
            </thead>
            <tbody>
              {displayStudents.map(function(student) {
                return (
                  <tr key={student.student_id}>
                    <td
                      onClick={function() { openReportCard(student); }}
                      style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)", cursor: "pointer" }}
                    >
                      {student.student_name}
                    </td>
                    {standards.map(function(code) {
                      var m = student.mastery[code];
                      var color = masteryColor(m ? m.percentage : null);
                      var clickable = !!m;
                      return (
                        <td
                          key={code}
                          onClick={function() { if (clickable) setSelectedCell({ student: student, standard: code, mastery: m }); }}
                          style={{
                            padding: "10px 8px",
                            textAlign: "center",
                            borderBottom: "1px solid var(--glass-border)",
                            borderLeft: "1px solid var(--glass-border)",
                            background: color.bg,
                            color: color.text,
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            cursor: clickable ? "pointer" : "default",
                          }}
                          title={clickable ? "Click to see contributing submissions" : "No data"}
                        >
                          {color.label}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Cell popover */}
      {selectedCell && (
        <div
          style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "var(--modal-bg)", display: "flex", alignItems: "center",
            justifyContent: "center", zIndex: 9999, padding: "20px",
          }}
          onClick={function() { setSelectedCell(null); }}
        >
          <div
            className="glass-card"
            style={{ maxWidth: "500px", width: "100%", padding: "24px", borderRadius: "16px" }}
            onClick={function(e) { e.stopPropagation(); }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
              <div>
                <h4 style={{ fontSize: "1rem", fontWeight: 700 }}>{selectedCell.student.student_name}</h4>
                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>{selectedCell.standard}</p>
              </div>
              <button onClick={function() { setSelectedCell(null); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
                {String.fromCharCode(10005)}
              </button>
            </div>
            <div style={{ fontSize: "0.85rem", marginBottom: "10px" }}>
              Mastery: <strong>{selectedCell.mastery.percentage}%</strong> ({selectedCell.mastery.points_earned}/{selectedCell.mastery.points_possible} pts across {selectedCell.mastery.question_count} questions)
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
              Contributing submissions
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "300px", overflowY: "auto" }}>
              {(selectedCell.mastery.contributing_submissions || []).map(function(c, i) {
                return (
                  <div key={i} style={{ padding: "8px 12px", background: "var(--glass-bg)", borderRadius: "6px", fontSize: "0.8rem" }}>
                    <div style={{ fontWeight: 600 }}>{c.title}</div>
                    <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                      {c.attempt_number ? 'Attempt ' + c.attempt_number + ' ' + String.fromCharCode(8226) + ' ' : ''}
                      {c.points_earned}/{c.points_possible} pts
                    </div>
                  </div>
                );
              })}
            </div>
            {selectedCell.mastery && selectedCell.mastery.percentage < 85 && (
              <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid var(--glass-border)" }}>
                <button
                  onClick={function() {
                    setRemediationTrigger({
                      standardCode: selectedCell.standard,
                      targetMode: "single_student",
                      targetStudentId: selectedCell.student.student_id,
                      targetStudentName: selectedCell.student.student_name,
                    });
                    setSelectedCell(null);
                  }}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "8px", fontSize: "0.85rem" }}
                >
                  Generate remediation
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Student Report Card drawer (Phase 2b) */}
      {selectedStudent && (
        <StudentReportCard
          classId={classId}
          studentId={selectedStudent.student_id}
          attemptMode={attemptMode}
          onClose={function() { setSelectedStudent(null); }}
        />
      )}

      {/* Remediation drawer (Phase 4) */}
      {remediationTrigger && (
        <RemediationDrawer
          open={!!remediationTrigger}
          onClose={function() { setRemediationTrigger(null); }}
          classId={classId}
          standardCode={remediationTrigger.standardCode}
          targetMode={remediationTrigger.targetMode}
          targetStudentId={remediationTrigger.targetStudentId}
          targetStudentName={remediationTrigger.targetStudentName}
        />
      )}

      <style>{
        ".phase4-header-cell:hover .phase4-header-remediate," +
        " .phase4-header-cell:focus-within .phase4-header-remediate" +
        " { opacity: 1 !important; }" +
        " .phase4-header-remediate:focus" +
        " { opacity: 1 !important; outline: 2px solid var(--accent-primary); }"
      }</style>
    </div>
  );
}
