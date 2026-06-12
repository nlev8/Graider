import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import StudentReportCard from "./StudentReportCard";
import RemediationDrawer from "./RemediationDrawer";
import RankTable from "./progress-rank-grid/RankTable";
import CellPopover from "./progress-rank-grid/CellPopover";
import { btnStyle } from "./progress-rank-grid/helpers";

/**
 * CQ wave-8 split: this shell owns ALL state (fetch, attempt mode, filters,
 * cell popover, report-card drawer, remediation trigger) + handlers +
 * guards; the mastery grid and cell popover are stateless components in
 * progress-rank-grid/*. Load-bearing: this parent CONDITIONALLY UNMOUNTS
 * RemediationDrawer via `{remediationTrigger && ...}` (its sibling
 * RemediationEffectiveness keeps it mounted and toggles `open` instead) —
 * the conditional drawer render below must stay as-is.
 */
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
  var [refreshKey, setRefreshKey] = useState(0);

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
  }, [classId, attemptMode, refreshKey]);

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
        <RankTable
          standards={standards}
          displayStudents={displayStudents}
          openReportCard={openReportCard}
          setSelectedCell={setSelectedCell}
          setRemediationTrigger={setRemediationTrigger}
        />
      )}

      {/* Cell popover (early-returns null until a cell is selected —
          stateless, so never-mounted vs render-null is behaviorally
          identical). */}
      <CellPopover
        selectedCell={selectedCell}
        setSelectedCell={setSelectedCell}
        setRemediationTrigger={setRemediationTrigger}
      />

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
          onPublished={function() { setRefreshKey(function(k) { return k + 1; }); }}
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
