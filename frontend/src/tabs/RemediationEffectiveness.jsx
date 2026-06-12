import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import RemediationDrawer from "./RemediationDrawer";
import RemediationCard from "./remediation-effectiveness/RemediationCard";
import RecallConfirmModal from "./remediation-effectiveness/RecallConfirmModal";

/**
 * Phase 4.2 #6 — Remediation Effectiveness dashboard.
 *
 * Per-(student × remediation) row showing before/after mastery delta on the
 * targeted standard, plus completion + attempt count. Per-row "Remediate
 * again" CTA opens RemediationDrawer in single-student mode.
 *
 * Spec: docs/superpowers/specs/2026-04-27-phase4.2-effectiveness-dashboard-design.md
 *
 * CQ wave-8 split: this shell owns ALL state (fetch, drawer, recall modal,
 * DOK expander) + handlers + guards; the per-remediation card and the recall
 * confirm modal are stateless components in remediation-effectiveness/*.
 * Load-bearing: this parent keeps RemediationDrawer MOUNTED and toggles
 * `open` (its sibling ProgressRankGrid conditionally unmounts it instead) —
 * the drawer render below must stay unconditional.
 */
export default function RemediationEffectiveness({ classId, addToast }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  // Drawer state for per-row "Remediate again" CTA.
  var [drawerOpen, setDrawerOpen] = useState(false);
  var [drawerStudentId, setDrawerStudentId] = useState(null);
  var [drawerStudentName, setDrawerStudentName] = useState("");
  var [drawerStandardCode, setDrawerStandardCode] = useState("");
  // Recall confirm modal state (Phase 4.2 #5). Holds the rem object whose
  // recall is awaiting confirmation; null when no modal is open.
  var [recallTarget, setRecallTarget] = useState(null);
  var [recallInFlight, setRecallInFlight] = useState(false);
  var [recallError, setRecallError] = useState(null);
  // Bumping `reloadKey` forces the fetch effect to re-run after the drawer
  // publishes a new remediation (matches ProgressRankGrid Phase 4.2 fix).
  var [reloadKey, setReloadKey] = useState(0);

  // Phase 4.3 Sprint 3: per-row DOK breakdown expander. Key = "<rem_id>:<sid>"
  // since the same student can appear across multiple remediation cards.
  var [expandedDokKey, setExpandedDokKey] = useState(null);

  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassRemediationEffectiveness(classId)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Failed to load effectiveness");
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || "Failed to load effectiveness");
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, reloadKey]);

  function openRemediateAgain(studentId, studentName, standardCode) {
    setDrawerStudentId(studentId);
    setDrawerStudentName(studentName || "");
    setDrawerStandardCode(standardCode || "");
    setDrawerOpen(true);
  }

  function onDrawerClose() {
    setDrawerOpen(false);
  }

  function onDrawerPublished() {
    // Refresh dashboard so the newly published remediation appears.
    setReloadKey(function(k) { return k + 1; });
  }

  // Phase 4.2 #5: Recall flow. Modal-confirmed; on success, toast + reload.
  function openRecallModal(rem) {
    setRecallTarget(rem);
    setRecallError(null);
  }
  function closeRecallModal() {
    if (recallInFlight) return;
    setRecallTarget(null);
    setRecallError(null);
  }
  function confirmRecall() {
    if (!recallTarget) return;
    setRecallInFlight(true);
    setRecallError(null);
    var rem = recallTarget;
    var submittedCount = (rem.rows || []).filter(function(r) { return r.completed; }).length;
    api.recallRemediation(classId, rem.remediation_id)
      .then(function(res) {
        if (!res || res.error || !res.recalled) {
          setRecallError((res && (res.detail || res.error)) || "Recall failed");
          return;
        }
        // Build toast text. Drop "N students had already submitted" if 0.
        var toastMsg = "Recalled.";
        if (submittedCount > 0) {
          toastMsg = "Recalled. " + submittedCount + " student"
            + (submittedCount === 1 ? "" : "s")
            + " had already submitted " + String.fromCharCode(8212)
            + " their work is preserved.";
        }
        if (typeof addToast === "function") addToast(toastMsg);
        setRecallTarget(null);
        // Re-fetch dashboard to pick up canonical state (is_active=false).
        setReloadKey(function(k) { return k + 1; });
      })
      .catch(function(e) {
        setRecallError((e && e.message) || "Recall failed");
      })
      .finally(function() { setRecallInFlight(false); });
  }

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading effectiveness...</p>
      </div>
    );
  }
  if (error) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{error}</div>;
  }
  if (!data) return null;

  var remediations = data.remediations || [];

  return (
    <div>
      <div className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
          Remediation Effectiveness {String.fromCharCode(8212)} {data.class_name}
        </h3>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0" }}>
          Did your recent remediations move student mastery? Each row shows
          before/after on the targeted standard.
        </p>
      </div>

      {remediations.length === 0 ? (
        <div className="glass-card" style={{ padding: "40px", textAlign: "center", color: "var(--text-secondary)" }}>
          <p style={{ fontSize: "0.95rem", marginBottom: "8px" }}>No remediations published yet.</p>
          <p style={{ fontSize: "0.85rem" }}>
            Use the Progress Rank grid to publish one.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {remediations.map(function(rem) {
            return (
              <RemediationCard
                key={rem.remediation_id}
                rem={rem}
                expandedDokKey={expandedDokKey}
                setExpandedDokKey={setExpandedDokKey}
                openRecallModal={openRecallModal}
                openRemediateAgain={openRemediateAgain}
              />
            );
          })}
        </div>
      )}

      <RemediationDrawer
        open={drawerOpen}
        onClose={onDrawerClose}
        classId={classId}
        standardCode={drawerStandardCode}
        targetMode="single_student"
        targetStudentId={drawerStudentId}
        targetStudentName={drawerStudentName}
        onPublished={onDrawerPublished}
      />

      {/* Phase 4.2 #5: Recall confirm modal (early-returns null until a
          recall is pending — stateless, so never-mounted vs render-null is
          behaviorally identical). */}
      <RecallConfirmModal
        recallTarget={recallTarget}
        recallError={recallError}
        recallInFlight={recallInFlight}
        closeRecallModal={closeRecallModal}
        confirmRecall={confirmRecall}
      />
    </div>
  );
}
