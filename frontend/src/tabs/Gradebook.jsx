import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import SubmissionDetail from "./SubmissionDetail";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

export default function Gradebook({ classId }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [missingOnly, setMissingOnly] = useState(false);
  var [selectedSubmissionId, setSelectedSubmissionId] = useState(null);

  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassGradebook(classId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load gradebook');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load gradebook');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, attemptMode]);

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading gradebook...</p>
      </div>
    );
  }
  if (error) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{error}</div>;
  }
  if (!data) return null;

  var students = data.students || [];
  var assessments = data.assessments || [];
  var grades = data.grades || {};

  var displayStudents = !missingOnly ? students : students.filter(function(s) {
    var row = grades[s.student_id] || {};
    return assessments.some(function(a) { return !row[a.content_id]; });
  });

  var btnStyle = function(active) {
    return {
      padding: "6px 14px", borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
    };
  };

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Gradebook {String.fromCharCode(8212)} {data.class_name}
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {students.length} students {String.fromCharCode(8226)} {assessments.length} assessments
      </p>

      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setMissingOnly(false); }} style={btnStyle(!missingOnly)}>All Students</button>
          <button onClick={function() { setMissingOnly(true); }} style={btnStyle(missingOnly)}>Missing Only</button>
        </div>
      </div>

      {students.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No students enrolled in this class yet.
        </p>
      ) : assessments.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No assessments published to this class yet.
        </p>
      ) : displayStudents.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          All students have submitted everything.
        </p>
      ) : (
        <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "600px" }}>
            <thead>
              <tr>
                <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 2, padding: "10px 14px", textAlign: "left", fontSize: "0.8rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>Student</th>
                {assessments.map(function(a) {
                  return (
                    <th key={a.content_id} style={{ padding: "10px 8px", fontSize: "0.7rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "100px", textAlign: "center" }}>
                      {a.title}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {displayStudents.map(function(student) {
                var row = grades[student.student_id] || {};
                return (
                  <tr key={student.student_id}>
                    <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>
                      {student.student_name}
                    </td>
                    {assessments.map(function(a) {
                      var cell = row[a.content_id];
                      var color = masteryColor(cell ? cell.percentage : null);
                      var clickable = !!cell;
                      return (
                        <td key={a.content_id}
                            onClick={function() { if (clickable) setSelectedSubmissionId(cell.submission_id); }}
                            style={{ padding: "10px 8px", textAlign: "center", borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", background: color.bg, color: color.text, fontSize: "0.8rem", fontWeight: 600, cursor: clickable ? "pointer" : "default" }}
                            title={clickable ? "Click to see this submission's detail" : "No submission"}>
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

      {selectedSubmissionId && (
        <SubmissionDetail
          submissionId={selectedSubmissionId}
          onClose={function() { setSelectedSubmissionId(null); }}
        />
      )}
    </div>
  );
}
