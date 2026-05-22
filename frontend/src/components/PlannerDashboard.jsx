import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function PlannerDashboard({ addToast, allTeacherTags, assignment, contentSubmissionsGroups, deletePublishedAssessment, deleteSavedAssessment, fetchAssessmentResults, fetchPublishedAssessments, fetchSavedAssessments, fetchSharedResources, fetchTeacherClasses, fetchTeacherTags, handleDeleteAllSharedResources, handleDeleteSharedResource, inProgressDrafts, itemMatchesTagFilter, loadSavedAssessment, loadingPublished, loadingResults, loadingSavedAssessments, loadingSharedResources, publishedAssessments, renderTagRow, savedAssessments, selectedAssessmentResults, selectedTagFilter, setAttemptDrawerStudent, setInProgressDrafts, setPublishedAssessments, setSelectedAssessmentResults, setSelectedTagFilter, setSharedResources, sharedResources, teacherClasses, toggleAssessmentStatus }) {
  return (
                    <div className="fade-in">
                      {/* Teacher's Classes */}
                      <div className="glass-card" style={{ padding: "20px", marginBottom: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                  <Icon name="School" size={20} />
                                  Your Classes
                              </h3>
                              <button onClick={fetchTeacherClasses} className="btn btn-secondary" style={{ padding: "8px 12px", fontSize: "0.85rem" }}>
                                  <Icon name="RefreshCw" size={16} /> Refresh
                              </button>
                          </div>
                          {teacherClasses.length === 0 ? (
                              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                                  No classes yet. Classes are created automatically when you sync your roster via Clever, ClassLink, or CSV import.
                              </p>
                          ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {teacherClasses.map(function(cls) {
                                      return (
                                          <div key={cls.id} style={{
                                              padding: "12px 15px",
                                              background: "rgba(255,255,255,0.03)",
                                              borderRadius: "10px",
                                              border: "1px solid rgba(255,255,255,0.1)",
                                              display: "flex",
                                              justifyContent: "space-between",
                                              alignItems: "center",
                                          }}>
                                              <div>
                                                  <div style={{ fontWeight: 600 }}>{cls.name}</div>
                                                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                                      {"Code: " + cls.join_code + " | " + (cls.subject || "No subject") + " | " + ((cls.class_students || [{}])[0]?.count || 0) + " students"}
                                                  </div>
                                              </div>
                                          </div>
                                      );
                                  })}
                              </div>
                          )}
                      </div>
                      {/* Global tag filter — Content Tagging */}
                      <div className="glass-card" style={{ padding: "12px 16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon name="Tag" size={16} style={{ color: "var(--text-secondary)" }} />
                        <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Filter by tag:</label>
                        <select
                          value={selectedTagFilter}
                          onChange={function(e) { setSelectedTagFilter(e.target.value); }}
                          className="input"
                          style={{ padding: "6px 12px", fontSize: "0.85rem", minWidth: "220px" }}
                        >
                          <option value="all">All content ({allTeacherTags.length} tags)</option>
                          {allTeacherTags.map(function(t) {
                            return <option key={t} value={t}>{t}</option>;
                          })}
                        </select>
                        {selectedTagFilter !== 'all' && (
                          <button
                            onClick={function() { setSelectedTagFilter('all'); }}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Clear
                          </button>
                        )}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: selectedAssessmentResults ? "1fr 1fr" : "1fr", gap: "25px" }}>
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

                        {/* Shared Resources Section */}
                        <div className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="BookOpen" size={20} />
                            Shared Resources
                          </h3>
                          {loadingSharedResources ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Loading...</p>
                          ) : sharedResources.length === 0 ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                              No shared resources yet. Use "Share with Class" on flashcards, study guides, or slide decks to share them with students.
                            </p>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {sharedResources.filter(itemMatchesTagFilter).map(function(res) {
                                var typeIcon = res.content_type === 'flashcards' ? 'Layers'
                                  : res.content_type === 'study_guide' ? 'FileText'
                                  : res.content_type === 'slide_deck' ? 'Monitor'
                                  : 'File';
                                var typeLabel = res.content_type === 'flashcards' ? 'Flashcards'
                                  : res.content_type === 'study_guide' ? 'Study Guide'
                                  : res.content_type === 'slide_deck' ? 'Slide Deck'
                                  : res.content_type;
                                var sameTitle = sharedResources.filter(function(r) { return r.title === res.title; });
                                var isFirst = sameTitle[0] && sameTitle[0].id === res.id;
                                return (
                                  <div key={res.id} style={{
                                    display: "flex", alignItems: "center", gap: "12px",
                                    padding: "10px 14px", borderRadius: "10px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                  }}>
                                    <Icon name={typeIcon} size={18} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {res.title}
                                      </div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                      </div>
                                      {renderTagRow(res, function(updates) {
                                        setSharedResources(function(prev) {
                                          return prev.map(function(r) { return r.id === res.id ? Object.assign({}, r, updates) : r; });
                                        });
                                      })}
                                    </div>
                                    <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                                      {isFirst && sameTitle.length > 1 && (
                                        <button
                                          onClick={function() { if (confirm('Delete "' + res.title + '" from all ' + sameTitle.length + ' classes?')) handleDeleteAllSharedResources(res.title); }}
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                                          title="Delete from all classes"
                                        >
                                          Delete All ({sameTitle.length})
                                        </button>
                                      )}
                                      <button
                                        onClick={function() { handleDeleteSharedResource(res.id, res.title + ' (' + res.class_name + ')'); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)", padding: "4px" }}
                                        title={"Delete from " + res.class_name}
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Submissions Detail Panel */}
                        {selectedAssessmentResults && (
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
                            {inProgressDrafts.length > 0 && (
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
                            )}

                            {/* Standards Summary Card */}
                            {selectedAssessmentResults && selectedAssessmentResults.submissions && selectedAssessmentResults.submissions.length > 0 && (() => {
                              var byStandard = {};
                              selectedAssessmentResults.submissions.forEach(function(sub) {
                                var mastery = sub.results && sub.results.standards_mastery;
                                if (!mastery) return;
                                Object.keys(mastery).forEach(function(code) {
                                  var m = mastery[code];
                                  // Phase 4.3 Sprint 2 — backend may emit either old flat shape or
                                  // new {overall, by_dok} shape (only Student Report Card route emits
                                  // by_dok in its response; the rest preserve flat — but defend at
                                  // every read site).
                                  var ov = (m && m.overall) ? m.overall : (m || {});
                                  if (!byStandard[code]) byStandard[code] = { earned: 0, possible: 0, question_count: ov.question_count };
                                  byStandard[code].earned += ov.points_earned || 0;
                                  byStandard[code].possible += ov.points_possible || 0;
                                });
                              });
                              var codes = Object.keys(byStandard);
                              if (codes.length === 0) return null;
                              return (
                                <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                                    <Icon name="Target" size={16} />
                                    Standards in this Assessment ({codes.length})
                                  </h4>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    {codes.map(function(code) {
                                      var s = byStandard[code];
                                      var pct = s.possible > 0 ? Math.round((s.earned / s.possible) * 100) : 0;
                                      var barColor = pct >= 80 ? "var(--success)" : pct >= 60 ? "var(--warning)" : "var(--danger)";
                                      return (
                                        <div key={code} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 12px", borderRadius: "8px", background: "var(--glass-bg)" }}>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, fontFamily: "monospace", minWidth: "100px" }}>{code}</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", minWidth: "70px" }}>{s.question_count} Q{s.question_count === 1 ? '' : 's'}</div>
                                          <div style={{ flex: 1, height: "6px", background: "var(--glass-bg)", borderRadius: "3px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                                            <div style={{ width: pct + "%", height: "100%", background: barColor, transition: "width 0.3s" }} />
                                          </div>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: "50px", textAlign: "right" }}>{pct}%</div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })()}

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
                        )}
                      </div>

                      {/* Saved Assessments Section */}
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
                    </div>
  );
}
