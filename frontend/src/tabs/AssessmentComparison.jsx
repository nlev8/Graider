import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import RemediationDrawer from "./RemediationDrawer";
import AssessmentPicker from "./assessment-comparison/AssessmentPicker";
import ComparisonResults from "./assessment-comparison/ComparisonResults";

// Shell for the Compare Assessments tab (CQ wave-8 split). Owns ALL state
// (selection, attempt mode, both fetch lifecycles, search, remediation
// trigger + reloadKey) and the two data effects with byte-identical dep
// arrays; the stateless children in assessment-comparison/ (picker, stat
// cards + box plot + heatmap, gradeColor) only render what they're handed.
export default function AssessmentComparison({ classId }) {
  var [available, setAvailable] = useState([]);
  var [bootstrapLoading, setBootstrapLoading] = useState(true);
  var [bootstrapError, setBootstrapError] = useState(null);
  var [selectedContentIds, setSelectedContentIds] = useState([]);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(false);
  var [error, setError] = useState(null);
  var [searchQuery, setSearchQuery] = useState('');
  // Phase 4.2 #10: heatmap remediate trigger state. Mirrors the
  // ProgressRankGrid pattern. reloadKey bumps the comparison fetch so a
  // successful publish reflects in the heatmap on the next pass.
  var [remediationTrigger, setRemediationTrigger] = useState(null);
  var [reloadKey, setReloadKey] = useState(0);

  // Bootstrap: fetch the list of class assessments via the gradebook endpoint.
  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setBootstrapLoading(true);
    setBootstrapError(null);
    setSelectedContentIds([]);
    setData(null);
    api.getClassGradebook(classId, 'latest')
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setBootstrapError((res && res.error) || 'Failed to load assessments');
          setAvailable([]);
        } else {
          // Gradebook returns both assessments and assignments. The compare endpoint
          // also enforces content_type='assessment' as a 403 guard, but we filter
          // client-side so non-assessments never appear in the picker.
          // (If the gradebook response omits content_type on a row, fall through —
          // the backend guard will catch it.)
          var assessmentsOnly = (res.assessments || []).filter(function(a) {
            return !a.content_type || a.content_type === 'assessment';
          });
          setAvailable(assessmentsOnly);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setBootstrapError((e && e.message) || 'Failed to load assessments');
      })
      .finally(function() { if (!cancelled) setBootstrapLoading(false); });
    return function() { cancelled = true; };
  }, [classId]);

  // Comparison fetch when selection is valid.
  useEffect(function() {
    if (selectedContentIds.length < 2 || selectedContentIds.length > 6) {
      setData(null);
      return;
    }
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassAssessmentComparison(classId, selectedContentIds, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load comparison');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load comparison');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, selectedContentIds, attemptMode, reloadKey]);

  function toggleSelection(contentId) {
    if (selectedContentIds.indexOf(contentId) >= 0) {
      setSelectedContentIds(selectedContentIds.filter(function(id) { return id !== contentId; }));
    } else if (selectedContentIds.length < 6) {
      setSelectedContentIds(selectedContentIds.concat([contentId]));
    }
  }

  var btnStyle = function(active) {
    return {
      padding: "6px 14px", borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
    };
  };

  if (bootstrapLoading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading assessments...</p>
      </div>
    );
  }
  if (bootstrapError) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{bootstrapError}</div>;
  }

  var orderedSelected = selectedContentIds.map(function(cid) {
    return available.find(function(a) { return a.content_id === cid; });
  }).filter(Boolean);

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Compare Assessments
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {selectedContentIds.length} of 6 selected {String.fromCharCode(8226)} pick 2-6 assessments
      </p>

      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
      </div>

      {/* Picker */}
      <AssessmentPicker
        available={available}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        selectedContentIds={selectedContentIds}
        toggleSelection={toggleSelection}
      />

      {/* Comparison output */}
      {selectedContentIds.length < 2 ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
          Pick at least 2 assessments to compare.
        </p>
      ) : loading ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>Loading comparison...</p>
      ) : error ? (
        <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>{error}</div>
      ) : data ? (
        <ComparisonResults
          data={data}
          orderedSelected={orderedSelected}
          setRemediationTrigger={setRemediationTrigger}
        />
      ) : null}

      {/* Phase 4.2 #10: hover/focus outline for red heatmap cells. Inline
          style would not trigger on :hover; one CSS block keeps the
          discoverability cue without restructuring the cell rendering. */}
      <style>{
        ".phase4-heatmap-red-clickable:hover {" +
        " outline: 2px solid var(--accent-primary); outline-offset: -2px; }" +
        ".phase4-heatmap-red-clickable:focus {" +
        " outline: 2px solid var(--accent-primary); outline-offset: -2px; }"
      }</style>

      {/* Phase 4.2 #10: RemediationDrawer mount, mirroring ProgressRankGrid. */}
      {remediationTrigger && (
        <RemediationDrawer
          open={!!remediationTrigger}
          onClose={function() { setRemediationTrigger(null); }}
          classId={classId}
          standardCode={remediationTrigger.standardCode}
          targetMode="red_tier_in_class"
          targetStudentId={null}
          targetStudentName=""
          onPublished={function() { setReloadKey(function(k) { return k + 1; }); }}
        />
      )}
    </div>
  );
}
