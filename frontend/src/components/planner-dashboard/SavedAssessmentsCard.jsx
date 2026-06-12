import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (Saved
// Assessments card). Stateless.
export default function SavedAssessmentsCard({ deleteSavedAssessment, fetchSavedAssessments, loadSavedAssessment, loadingSavedAssessments, savedAssessments }) {
  return (
                      <div className="glass-card" style={{ padding: "20px", marginTop: "25px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="Archive" size={20} />
                            Saved Assessments
                          </h3>
                          <button
                            onClick={fetchSavedAssessments}
                            className="btn btn-secondary"
                            style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                            disabled={loadingSavedAssessments}
                          >
                            <Icon name={loadingSavedAssessments ? "Loader2" : "RefreshCw"} size={16} className={loadingSavedAssessments ? "spin" : ""} />
                            Refresh
                          </button>
                        </div>

                        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                          Load a saved assessment to view, modify, or publish it for makeup exams.
                        </p>

                        {loadingSavedAssessments ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="Loader2" size={32} className="spin" />
                            <p style={{ marginTop: "10px" }}>Loading saved assessments...</p>
                          </div>
                        ) : savedAssessments.length === 0 ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="FolderOpen" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                            <p>No saved assessments.</p>
                            <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>Generate an assessment and use "Save for Later" to save it.</p>
                          </div>
                        ) : (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
                            {savedAssessments.map((assessment) => (
                              <div
                                key={assessment.filename}
                                style={{
                                  padding: "15px",
                                  background: "rgba(255,255,255,0.03)",
                                  borderRadius: "10px",
                                  border: "1px solid rgba(255,255,255,0.1)",
                                }}
                              >
                                <div style={{ fontWeight: 600, marginBottom: "8px" }}>{assessment.name}</div>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                                  <Icon name="FileText" size={14} />
                                  {assessment.question_count || '?'} questions
                                  <span>·</span>
                                  <Icon name="Target" size={14} />
                                  {assessment.total_points || '?'} pts
                                </div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                                  Saved: {new Date(assessment.saved_at).toLocaleDateString()}
                                </div>
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <button
                                    onClick={() => loadSavedAssessment(assessment.filename)}
                                    className="btn btn-primary"
                                    style={{ padding: "6px 12px", fontSize: "0.85rem", flex: 1 }}
                                  >
                                    <Icon name="Download" size={14} />
                                    Load
                                  </button>
                                  <button
                                    onClick={() => deleteSavedAssessment(assessment.filename)}
                                    className="btn"
                                    style={{ padding: "6px 10px", fontSize: "0.85rem", background: "rgba(239, 68, 68, 0.2)", color: "#ef4444" }}
                                    title="Delete"
                                  >
                                    <Icon name="Trash2" size={14} />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
  );
}
