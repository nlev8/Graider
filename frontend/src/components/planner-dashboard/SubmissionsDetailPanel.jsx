import React from "react";
import Icon from "../Icon";
import InProgressDraftsCard from "./InProgressDraftsCard";
import StandardsSummaryCard from "./StandardsSummaryCard";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (Submissions
// Detail panel). The original `{selectedAssessmentResults && ...}` guard
// becomes the early return below (house pattern); the In Progress and
// Standards Summary sub-cards moved to sibling components with their own
// original guards as early returns.
export default function SubmissionsDetailPanel({ addToast, contentSubmissionsGroups, inProgressDrafts, loadingResults, selectedAssessmentResults, setAttemptDrawerStudent, setInProgressDrafts, setSelectedAssessmentResults }) {
  if (!(selectedAssessmentResults)) return null;
  return (
                          <div className="glass-card" style={{ padding: "20px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="BarChart3" size={20} />
                                {selectedAssessmentResults.title}
                              </h3>
                              <button
                                onClick={() => setSelectedAssessmentResults(null)}
                                style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                              >
                                <Icon name="X" size={20} />
                              </button>
                            </div>

                            {/* Stats Summary */}
                            {selectedAssessmentResults.submissions.length > 0 && (
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "15px", marginBottom: "20px" }}>
                                <div style={{ padding: "15px", background: "rgba(34, 197, 94, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#22c55e" }}>
                                    {selectedAssessmentResults.submissions.length}
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Submissions</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(99, 102, 241, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#6366f1" }}>
                                    {Math.round(selectedAssessmentResults.submissions.reduce((sum, s) => sum + (s.percentage || 0), 0) / selectedAssessmentResults.submissions.length)}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Avg Score</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f59e0b" }}>
                                    {Math.max(...selectedAssessmentResults.submissions.map(s => s.percentage || 0))}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>High Score</div>
                                </div>
                              </div>
                            )}

                            {/* In Progress Drafts */}
                            <InProgressDraftsCard
                              addToast={addToast}
                              inProgressDrafts={inProgressDrafts}
                              setInProgressDrafts={setInProgressDrafts}
                            />

                            {/* Standards Summary Card */}
                            <StandardsSummaryCard selectedAssessmentResults={selectedAssessmentResults} />

                            {/* Student Submissions List */}
                            {loadingResults ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="Loader2" size={32} className="spin" />
                              </div>
                            ) : selectedAssessmentResults.submissions.length === 0 ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="UserX" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                                <p>No submissions yet.</p>
                                <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>
                                  Share code <strong>{selectedAssessmentResults.joinCode}</strong> with students.
                                </p>
                              </div>
                            ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "400px", overflowY: "auto" }}>
                                {selectedAssessmentResults.submissions.map((submission, idx) => (
                                  <div
                                    key={idx}
                                    style={{
                                      padding: "12px 15px",
                                      background: "rgba(255,255,255,0.03)",
                                      borderRadius: "8px",
                                      border: "1px solid rgba(255,255,255,0.1)",
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "center",
                                    }}
                                  >
                                    <div>
                                      <div style={{ fontWeight: 600, display: "flex", alignItems: "center" }}>
                                        {submission.student_name}
                                        {(() => {
                                          var group = contentSubmissionsGroups.find(function(g) { return g.student_id === submission.student_id || g.student_name === submission.student_name; });
                                          if (!group || group.attempts.length <= 1) return null;
                                          var curAttempt = (submission.results && submission.results.attempt_number) || submission.attempt_number || 1;
                                          return (
                                            <button
                                              onClick={function(e) { e.stopPropagation(); setAttemptDrawerStudent(group); }}
                                              style={{ fontSize: "0.7rem", padding: "3px 8px", borderRadius: "10px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)", color: "var(--text-secondary)", cursor: "pointer", marginLeft: "8px" }}
                                              title="View all attempts"
                                            >
                                              Attempt {curAttempt} of {group.attempts.length}
                                            </button>
                                          );
                                        })()}
                                      </div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {new Date(submission.submitted_at).toLocaleString()}
                                        {submission.time_taken_seconds && (
                                          <span> · {Math.floor(submission.time_taken_seconds / 60)}m {submission.time_taken_seconds % 60}s</span>
                                        )}
                                      </div>
                                    </div>
                                    <div style={{ textAlign: "right" }}>
                                      <div style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 700,
                                        color: submission.percentage >= 80 ? "#22c55e" : submission.percentage >= 60 ? "#f59e0b" : "#ef4444"
                                      }}>
                                        {submission.percentage?.toFixed(0) || 0}%
                                      </div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {submission.score}/{submission.total_points} pts
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
  );
}
