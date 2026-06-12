import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (the two
// published-content sections — assessments + assignments). The section-config
// array and its .map moved here intact; the two cards render as fragment
// children of the orchestrator's grid, exactly as the inline array did.
export default function PublishedContentList({ deletePublishedAssessment, fetchAssessmentResults, fetchPublishedAssessments, fetchSharedResources, fetchTeacherTags, itemMatchesTagFilter, loadingPublished, publishedAssessments, renderTagRow, selectedAssessmentResults, setPublishedAssessments, toggleAssessmentStatus }) {
  return (
                        <>
                        {/* Published Content Lists — separated by content type */}
                        {[
                          { type: "assessment", label: "Published Assessments", icon: "ClipboardList", emptyText: "No published assessments yet.", emptyHint: "Generate an assessment and click \"Publish to Portal\" to get started." },
                          { type: "assignment", label: "Published Assignments", icon: "FileText", emptyText: "No published assignments yet.", emptyHint: "Generate an assignment and click \"Publish to Portal\" to get started." },
                        ].map((section) => {
                          var sectionItems = publishedAssessments.filter(function(a) {
                            return (a.content_type || "assessment") === section.type && itemMatchesTagFilter(a);
                          });
                          return (
                        <div key={section.type} className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                              <Icon name={section.icon} size={20} />
                              {section.label}
                              <span style={{ fontSize: "0.75rem", fontWeight: 400, color: "var(--text-secondary)", background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "10px" }}>{sectionItems.length}</span>
                            </h3>
                            {section.type === "assessment" && (
                            <button
                              onClick={function() { fetchPublishedAssessments(); fetchSharedResources(); fetchTeacherTags(); }}
                              className="btn btn-secondary"
                              style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                              disabled={loadingPublished}
                            >
                              <Icon name={loadingPublished ? "Loader2" : "RefreshCw"} size={16} className={loadingPublished ? "spin" : ""} />
                              Refresh
                            </button>
                            )}
                          </div>

                          {loadingPublished ? (
                            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                              <Icon name="Loader2" size={32} className="spin" />
                              <p style={{ marginTop: "10px" }}>Loading...</p>
                            </div>
                          ) : sectionItems.length === 0 ? (
                            <div style={{ textAlign: "center", padding: "30px", color: "var(--text-secondary)" }}>
                              <Icon name="FileQuestion" size={36} style={{ opacity: 0.5, marginBottom: "10px" }} />
                              <p style={{ fontSize: "0.9rem" }}>{section.emptyText}</p>
                              <p style={{ fontSize: "0.8rem", marginTop: "5px", opacity: 0.7 }}>{section.emptyHint}</p>
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              {sectionItems.map((assessment) => (
                                <div
                                  key={assessment.join_code}
                                  style={{
                                    padding: "15px",
                                    background: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "rgba(139, 92, 246, 0.2)"
                                      : "rgba(255,255,255,0.03)",
                                    borderRadius: "10px",
                                    border: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "1px solid var(--accent-primary)"
                                      : "1px solid rgba(255,255,255,0.1)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                  onClick={() => fetchAssessmentResults(assessment.join_code)}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontWeight: 600, marginBottom: "5px" }}>{assessment.title}</div>
                                      <div style={{ display: "flex", alignItems: "center", gap: "15px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Hash" size={14} />
                                          {assessment.join_code}
                                        </span>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Users" size={14} />
                                          {assessment.submission_count || 0} submissions
                                        </span>
                                        {assessment.period && (
                                          <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                            <Icon name="Clock" size={14} />
                                            {assessment.period}
                                          </span>
                                        )}
                                      </div>
                                      {assessment.is_makeup && (
                                        <span
                                          style={{
                                            marginTop: "8px",
                                            padding: "3px 8px",
                                            background: "rgba(245, 158, 11, 0.2)",
                                            color: "#f59e0b",
                                            borderRadius: "4px",
                                            fontSize: "0.75rem",
                                            fontWeight: 600,
                                          }}
                                        >
                                          Makeup Exam
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          borderRadius: "12px",
                                          fontSize: "0.75rem",
                                          fontWeight: 600,
                                          background: assessment.is_active ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)",
                                          color: assessment.is_active ? "#22c55e" : "#ef4444",
                                        }}
                                      >
                                        {assessment.is_active ? "Active" : "Closed"}
                                      </span>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); toggleAssessmentStatus(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                                        title={assessment.is_active ? "Deactivate" : "Activate"}
                                      >
                                        <Icon name={assessment.is_active ? "Pause" : "Play"} size={16} />
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); deletePublishedAssessment(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px", color: "#ef4444" }}
                                        title="Delete"
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                  <div style={{ marginTop: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                    Created: {new Date(assessment.created_at).toLocaleDateString()}
                                  </div>
                                  {renderTagRow(assessment, function(updates) {
                                    setPublishedAssessments(function(prev) {
                                      return prev.map(function(a) {
                                        if (a.join_code === assessment.join_code || a.id === assessment.id) return Object.assign({}, a, updates);
                                        return a;
                                      });
                                    });
                                  })}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                          );
                        })}
                        </>
  );
}
