import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import RemediationBadges from "../components/RemediationBadges";

function gradeColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

function formatDate(iso) {
  if (!iso) return String.fromCharCode(8212);
  try {
    var d = new Date(iso);
    return (d.getMonth() + 1) + "/" + d.getDate();
  } catch (e) {
    return String.fromCharCode(8212);
  }
}

export default function SubmissionDetail({ submissionId, onClose }) {
  // Local state — attempt selector mutates this, NOT the prop
  var [activeSubmissionId, setActiveSubmissionId] = useState(submissionId);
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [expandedQuestionIndex, setExpandedQuestionIndex] = useState(null);

  // Re-sync local state if prop changes (e.g., parent opens drawer with different submission)
  useEffect(function() { setActiveSubmissionId(submissionId); }, [submissionId]);

  useEffect(function() {
    if (!activeSubmissionId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    // NOTE: do NOT reset expandedQuestionIndex on attempt switch — spec says
    // local activeSubmissionId changes keep the drawer mounted and preserve
    // the user's expanded question. Reset only when the parent fully unmounts
    // the drawer (which happens via onClose).
    api.getSubmissionDetail(activeSubmissionId)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load submission');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load submission');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [activeSubmissionId]);

  useEffect(function() {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return function() { window.removeEventListener('keydown', onKey); };
  }, [onClose]);

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 9500, display: "flex", justifyContent: "flex-end" }}
      onClick={onClose}
    >
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)" }} />
      <div className="glass-card"
           style={{ position: "relative", width: "min(600px, 100vw)", height: "100%", background: "var(--card-bg)", borderLeft: "1px solid var(--glass-border)", boxShadow: "-4px 0 20px rgba(0,0,0,0.2)", padding: "24px", overflowY: "auto" }}
           onClick={function(e) { e.stopPropagation(); }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{data ? data.student_name : 'Submission'}</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
              {data ? data.content_title : ''}
            </p>
            {/* Phase 4.2 #7: remediation badges describe the content (not the
                student), so they live below the content_title line. */}
            {data && <RemediationBadges item={data} />}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.4rem" }}>
            {String.fromCharCode(10005)}
          </button>
        </div>

        {loading && <p style={{ color: "var(--text-secondary)" }}>Loading...</p>}
        {error && <div style={{ color: "var(--danger)" }}>{error}</div>}

        {data && !loading && !error && (
          <div>
            <div style={{ marginBottom: "16px", padding: "12px", background: "var(--glass-bg)", borderRadius: "8px" }}>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{data.percentage}%</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                {data.points_earned}/{data.points_possible} pts {String.fromCharCode(8226)} attempt {data.attempt_number} of {data.total_attempts} {String.fromCharCode(8226)} submitted {formatDate(data.submitted_at)}
              </div>
            </div>

            {data.sibling_attempts && data.sibling_attempts.length > 1 && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "6px" }}>Switch attempt</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {data.sibling_attempts.map(function(a) {
                    var isActive = a.submission_id === activeSubmissionId;
                    return (
                      <button key={a.submission_id}
                              onClick={function() { setActiveSubmissionId(a.submission_id); }}
                              disabled={isActive}
                              style={{ padding: "4px 10px", fontSize: "0.75rem", borderRadius: "6px", border: "1px solid var(--glass-border)", background: isActive ? "rgba(99,102,241,0.15)" : "var(--glass-bg)", color: isActive ? "var(--accent-primary)" : "var(--text-secondary)", cursor: isActive ? "default" : "pointer" }}>
                        Attempt {a.attempt_number} ({a.percentage}%)
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Per-question breakdown</h4>
            {(!data.questions || data.questions.length === 0) ? (
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Per-question detail not available for this submission.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {data.questions.map(function(q, i) {
                  var qPct = q.points_possible > 0 ? Math.round((q.points_earned / q.points_possible) * 100) : null;
                  var color = gradeColor(qPct);
                  var isExpanded = expandedQuestionIndex === i;
                  return (
                    <div key={i} style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "10px 12px", background: color.bg }}>
                      <div onClick={function() { setExpandedQuestionIndex(isExpanded ? null : i); }}
                           style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", alignItems: "center" }}>
                        <div style={{ flex: 1, fontSize: "0.85rem", color: color.text, fontWeight: 600 }}>
                          {(i + 1) + ". " + (q.question_text || '(no question text)')}
                        </div>
                        <div style={{ fontWeight: 700, color: color.text, fontSize: "0.9rem", marginLeft: "10px" }}>
                          {q.points_earned}/{q.points_possible}
                        </div>
                      </div>
                      {isExpanded && (
                        <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px solid var(--glass-border)", display: "flex", flexDirection: "column", gap: "8px" }}>
                          <div style={{ fontSize: "0.8rem" }}>
                            <strong style={{ color: "var(--text-secondary)" }}>Student answer:</strong>{" "}
                            <span>{q.student_answer || '(blank)'}</span>
                          </div>
                          {q.correct_answer != null && (
                            <div style={{ fontSize: "0.8rem" }}>
                              <strong style={{ color: "var(--text-secondary)" }}>Correct answer:</strong>{" "}
                              <span>{q.correct_answer}</span>
                            </div>
                          )}
                          {q.ai_feedback && (
                            <div style={{ fontSize: "0.8rem" }}>
                              <strong style={{ color: "var(--text-secondary)" }}>AI feedback:</strong>{" "}
                              <span>{q.ai_feedback}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            <p style={{ marginTop: "20px", fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>
              Read-only view. Manual grade overrides will arrive in a future phase.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
