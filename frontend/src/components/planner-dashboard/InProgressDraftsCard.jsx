import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (In Progress
// drafts card inside the submissions detail panel). The original
// `{inProgressDrafts.length > 0 && ...}` guard becomes the early return below
// (house pattern).
export default function InProgressDraftsCard({ addToast, inProgressDrafts, setInProgressDrafts }) {
  if (!(inProgressDrafts.length > 0)) return null;
  return (
                              <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                                  <Icon name="Clock" size={16} />
                                  In Progress ({inProgressDrafts.length})
                                </h4>
                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                  {inProgressDrafts.map(function(d) {
                                    var elapsedMin = Math.floor((d.elapsed_seconds || 0) / 60);
                                    return (
                                      <div key={d.submission_id} style={{
                                        display: "flex", alignItems: "center", justifyContent: "space-between",
                                        padding: "10px 14px", borderRadius: "8px",
                                        background: "var(--warning-bg)", border: "1px solid var(--warning-border)",
                                      }}>
                                        <div>
                                          <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{d.student_name}</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                            {d.answered_count} questions answered {String.fromCharCode(8226)} {elapsedMin} min elapsed
                                          </div>
                                        </div>
                                        <button
                                          onClick={async function() {
                                            if (!confirm('End ' + d.student_name + "'s attempt? Their current answers will be submitted.")) return;
                                            try {
                                              var res = await api.endStudentAttempt(d.submission_id);
                                              if (res.success) {
                                                addToast('Ended attempt for ' + d.student_name, 'success');
                                                setInProgressDrafts(function(prev) { return prev.filter(function(x) { return x.submission_id !== d.submission_id; }); });
                                              } else {
                                                addToast(res.error || 'Failed to end attempt', 'error');
                                              }
                                            } catch (e) {
                                              addToast('Failed: ' + e.message, 'error');
                                            }
                                          }}
                                          className="btn btn-secondary"
                                          style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                                        >
                                          End attempt
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
  );
}
