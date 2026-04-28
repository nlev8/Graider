import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import RemediationDrawer from "./RemediationDrawer";

/**
 * Phase 4.2 #6 — Remediation Effectiveness dashboard.
 *
 * Per-(student × remediation) row showing before/after mastery delta on the
 * targeted standard, plus completion + attempt count. Per-row "Remediate
 * again" CTA opens RemediationDrawer in single-student mode.
 *
 * Spec: docs/superpowers/specs/2026-04-27-phase4.2-effectiveness-dashboard-design.md
 */

function deltaColor(delta) {
  if (delta == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (delta >= 10) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: "+" + delta + "%" };
  if (delta >= 0) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: "+" + delta + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: delta + "%" };
}

function pctText(pct) {
  if (pct == null) return String.fromCharCode(8212);
  return pct + "%";
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch (e) {
    return "";
  }
}

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
              <div key={rem.remediation_id} className="glass-card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
                  <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0 }}>{rem.title}</h4>
                  <span style={{
                    fontFamily: "monospace", fontSize: "0.78rem", padding: "3px 8px",
                    borderRadius: "6px", background: "rgba(99,102,241,0.15)",
                    color: "var(--accent-primary)", fontWeight: 600,
                  }}>{rem.standard_code}</span>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                    Published {formatDate(rem.created_at)} {String.fromCharCode(8226)} {rem.target_count} student{rem.target_count === 1 ? "" : "s"}
                  </span>
                  {/* Phase 4.2 #5: Recall button (or Recalled badge if already inactive). */}
                  <div style={{ marginLeft: "auto" }}>
                    {rem.is_active === false ? (
                      <span style={{
                        fontSize: "0.78rem", padding: "3px 10px", borderRadius: "6px",
                        background: "rgba(239,68,68,0.12)", color: "var(--danger)", fontWeight: 700,
                      }}>Recalled</span>
                    ) : (
                      <button
                        onClick={function() { openRecallModal(rem); }}
                        className="btn"
                        style={{
                          padding: "5px 12px", fontSize: "0.8rem", fontWeight: 600,
                          background: "transparent", color: "var(--danger)",
                          border: "1px solid var(--danger)",
                        }}
                      >Recall</button>
                    )}
                  </div>
                </div>

                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                    <thead>
                      <tr>
                        <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "8px 12px", textAlign: "left", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>Student</th>
                        <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>Before</th>
                        <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>After</th>
                        <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>{String.fromCharCode(916)}</th>
                        <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "100px" }}>Completed</th>
                        <th style={{ padding: "8px 10px", textAlign: "center", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "80px" }}>Attempts</th>
                        <th style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "150px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(rem.rows || []).map(function(row) {
                        var d = deltaColor(row.delta);
                        var beforeBadge = row.before == null
                          ? <span style={{ fontSize: "0.72rem", padding: "2px 6px", borderRadius: "4px", background: "var(--glass-bg)", color: "var(--text-muted)" }}>No baseline</span>
                          : pctText(row.before);
                        return (
                          <tr key={row.student_id}>
                            <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 12px", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>{row.student_name || "(unknown)"}</td>
                            <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{beforeBadge}</td>
                            <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{pctText(row.after)}</td>
                            <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>
                              <span style={{
                                display: "inline-block", padding: "3px 10px", borderRadius: "6px",
                                background: d.bg, color: d.text, fontWeight: 700, fontSize: "0.82rem",
                              }}>{d.label}</span>
                            </td>
                            <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>
                              {row.completed
                                ? <span style={{ color: "var(--success)", fontWeight: 600 }}>Yes</span>
                                : <span style={{ color: "var(--text-muted)" }}>No</span>}
                            </td>
                            <td style={{ padding: "10px", textAlign: "center", borderBottom: "1px solid var(--glass-border)" }}>{row.attempt_count}</td>
                            <td style={{ padding: "10px", textAlign: "right", borderBottom: "1px solid var(--glass-border)" }}>
                              <button
                                onClick={function() { openRemediateAgain(row.student_id, row.student_name, rem.standard_code); }}
                                className="btn"
                                style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
                              >Remediate again</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
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

      {/* Phase 4.2 #5: Recall confirm modal. Inline; ~30 LOC. */}
      {recallTarget && (
        <div
          onClick={closeRecallModal}
          style={{
            position: "fixed", inset: 0, zIndex: 9600,
            background: "rgba(0,0,0,0.5)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            onClick={function(e) { e.stopPropagation(); }}
            className="glass-card"
            style={{ maxWidth: "440px", width: "100%", padding: "24px" }}
          >
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginTop: 0, marginBottom: "12px" }}>
              Recall this remediation?
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
              {(function() {
                var n = (recallTarget.rows || []).filter(function(r) { return r.completed; }).length;
                if (n > 0) {
                  return (
                    <>
                      <strong>{n} student{n === 1 ? "" : "s"} already submitted</strong>
                      {" " + String.fromCharCode(8212) + " their work is preserved. They'll just no longer see it in their dashboard."}
                    </>
                  );
                }
                return "Students will no longer see it in their dashboard.";
              })()}
            </p>
            {recallError && (
              <div style={{
                padding: "10px 12px", borderRadius: "6px", marginTop: "12px",
                background: "rgba(239,68,68,0.12)", color: "var(--danger)", fontSize: "0.85rem",
              }}>{recallError}</div>
            )}
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "20px" }}>
              <button
                onClick={closeRecallModal}
                disabled={recallInFlight}
                className="btn"
                style={{ padding: "8px 16px", fontSize: "0.85rem", opacity: recallInFlight ? 0.5 : 1 }}
              >Cancel</button>
              <button
                onClick={confirmRecall}
                disabled={recallInFlight}
                className="btn"
                style={{
                  padding: "8px 16px", fontSize: "0.85rem", fontWeight: 600,
                  background: "var(--danger)", color: "white", border: "none",
                  opacity: recallInFlight ? 0.6 : 1,
                }}
              >{recallInFlight ? "Recalling..." : "Recall"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
