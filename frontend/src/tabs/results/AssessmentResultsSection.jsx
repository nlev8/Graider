import React, { useState } from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import AssessmentDetailPanel from "./AssessmentDetailPanel";

export default function AssessmentResultsSection({
  assessmentResults,
  setAssessmentResults,
  config,
  addToast,
}) {
  var _assessmentSectionOpen = useState(true);
  var assessmentSectionOpen = _assessmentSectionOpen[0];
  var setAssessmentSectionOpen = _assessmentSectionOpen[1];
  var _assessmentCategoryFilter = useState('all');
  var assessmentCategoryFilter = _assessmentCategoryFilter[0];
  var setAssessmentCategoryFilter = _assessmentCategoryFilter[1];
  var _expandedAssessmentId = useState(null);
  var expandedAssessmentId = _expandedAssessmentId[0];
  var setExpandedAssessmentId = _expandedAssessmentId[1];
  var _assessmentStudentSort = useState({field: 'student_name', dir: 'asc'});
  var assessmentStudentSort = _assessmentStudentSort[0];
  var setAssessmentStudentSort = _assessmentStudentSort[1];
  var _questionBreakdownOpen = useState(false);
  var questionBreakdownOpen = _questionBreakdownOpen[0];
  var setQuestionBreakdownOpen = _questionBreakdownOpen[1];

  var filteredAssessments = (assessmentResults || []).filter(function(a) {
    if (assessmentCategoryFilter === 'all') return true;
    return a.assessment_category === assessmentCategoryFilter;
  });

  return (
                  <div style={{ marginBottom: "20px" }}>
                    <div
                      onClick={function() { setAssessmentSectionOpen(!assessmentSectionOpen); }}
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "12px 16px",
                        background: "rgba(139,92,246,0.08)",
                        border: "1px solid rgba(139,92,246,0.2)",
                        borderRadius: assessmentSectionOpen ? "10px 10px 0 0" : "10px",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon name={assessmentSectionOpen ? "ChevronDown" : "ChevronRight"} size={16} color="#8b5cf6" />
                        <span style={{ fontWeight: 700, fontSize: "1rem", color: "#8b5cf6" }}>Assessment Results</span>
                        <span style={{
                          padding: "2px 8px", borderRadius: "10px", fontSize: "0.75rem",
                          background: "rgba(139,92,246,0.2)", color: "#a78bfa",
                        }}>{filteredAssessments.length + ' assessment' + (filteredAssessments.length !== 1 ? 's' : '')}</span>
                      </div>
                      <div style={{ display: "flex", gap: "6px" }} onClick={function(e) { e.stopPropagation(); }}>
                        {['all', 'formative', 'summative'].map(function(cat) {
                          var isActive = assessmentCategoryFilter === cat;
                          var label = cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1);
                          return React.createElement('button', {
                            key: cat,
                            onClick: function() { setAssessmentCategoryFilter(cat); },
                            style: {
                              padding: "4px 10px", borderRadius: "6px", border: "none",
                              fontSize: "0.75rem", fontWeight: isActive ? 600 : 400, cursor: "pointer",
                              background: isActive ? "#7c3aed" : "rgba(255,255,255,0.08)",
                              color: isActive ? "white" : "var(--text-secondary)",
                            }
                          }, label);
                        })}
                      </div>
                    </div>

                    {assessmentSectionOpen && (
                    <div style={{
                      background: "var(--glass-bg)",
                      border: "1px solid var(--glass-border)",
                      borderTop: "none",
                      borderRadius: "0 0 10px 10px",
                      overflow: "hidden",
                    }}>
                      {filteredAssessments.length === 0 ? (
                        <div style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                          {(assessmentResults || []).length === 0
                            ? 'No assessments published yet. Publish an assessment to see results here.'
                            : 'No ' + assessmentCategoryFilter + ' assessments found.'}
                        </div>
                      ) : (
                        <div>
                          <div style={{
                            display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 0.8fr",
                            padding: "10px 16px", fontSize: "0.75rem", color: "var(--text-secondary)",
                            fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px",
                            borderBottom: "1px solid var(--glass-border)",
                          }}>
                            <span>Assessment</span><span>Type</span><span>Submissions</span>
                            <span>Avg Score</span><span>Status</span><span></span>
                          </div>

                          {filteredAssessments.map(function(assessment) {
                            return (
                              <AssessmentRow
                                key={assessment.id}
                                assessment={assessment}
                                expandedAssessmentId={expandedAssessmentId}
                                setExpandedAssessmentId={setExpandedAssessmentId}
                                assessmentStudentSort={assessmentStudentSort}
                                setAssessmentStudentSort={setAssessmentStudentSort}
                                questionBreakdownOpen={questionBreakdownOpen}
                                setQuestionBreakdownOpen={setQuestionBreakdownOpen}
                                config={config}
                                addToast={addToast}
                                setAssessmentResults={setAssessmentResults}
                              />
                            );
                          })}
                        </div>
                      )}
                    </div>
                    )}
                  </div>
  );
}

function AssessmentRow({
  assessment,
  expandedAssessmentId,
  setExpandedAssessmentId,
  assessmentStudentSort,
  setAssessmentStudentSort,
  questionBreakdownOpen,
  setQuestionBreakdownOpen,
  config,
  addToast,
  setAssessmentResults,
}) {
                            var isExpanded = expandedAssessmentId === assessment.id;
                            var stats = assessment.stats || {};
                            var isSummative = assessment.assessment_category === 'summative';
                            var subText = assessment.source === 'join_code'
                              ? (assessment.period ? assessment.period + ' · ' : '') + 'Code: ' + assessment.join_code
                              : (assessment.period || 'Class-based');
                            var publishDate = assessment.published_at ? new Date(assessment.published_at).toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : '';

                            return React.createElement('div', {key: assessment.id}, [
                              React.createElement('div', {
                                key: 'row',
                                style: {
                                  display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 0.8fr",
                                  padding: "12px 16px", alignItems: "center",
                                  borderBottom: "1px solid var(--glass-border)",
                                  background: isExpanded ? "rgba(139,92,246,0.05)" : "transparent",
                                },
                              }, [
                                React.createElement('div', {key: 'title'}, [
                                  React.createElement('div', {key: 't', style: {fontWeight: 600, fontSize: "0.9rem"}}, assessment.title),
                                  React.createElement('div', {key: 's', style: {fontSize: "0.75rem", color: "var(--text-secondary)"}}, publishDate + (subText ? ' · ' + subText : '')),
                                ]),
                                React.createElement('span', {
                                  key: 'type',
                                  style: {
                                    padding: "3px 10px", borderRadius: "12px", fontSize: "0.75rem", fontWeight: 600,
                                    width: "fit-content",
                                    background: isSummative ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
                                    color: isSummative ? "#ef4444" : "#22c55e",
                                  }
                                }, isSummative ? 'Summative' : 'Formative'),
                                React.createElement('span', {key: 'subs', style: {fontSize: "0.9rem"}},
                                  stats.expected_submissions
                                    ? stats.total_submissions + '/' + stats.expected_submissions
                                    : String(stats.total_submissions || 0)
                                ),
                                React.createElement('span', {
                                  key: 'avg',
                                  style: {
                                    fontWeight: 600, fontSize: "0.9rem",
                                    color: stats.average_score == null ? "var(--text-secondary)"
                                      : stats.average_score >= 80 ? "#22c55e"
                                      : stats.average_score >= 60 ? "#f59e0b" : "#ef4444",
                                  }
                                }, stats.average_score != null ? stats.average_score + '%' : '—'),
                                React.createElement('span', {
                                  key: 'status',
                                  style: {
                                    fontSize: "0.85rem",
                                    color: stats.pending_count > 0 ? "#f59e0b" : "#22c55e",
                                  }
                                }, stats.pending_count > 0 ? stats.pending_count + ' pending' : 'Complete'),
                                React.createElement('div', {key: 'actions', style: {display: "flex", gap: "10px", alignItems: "center"}}, [
                                  React.createElement('span', {
                                    key: 'details',
                                    onClick: function() { setExpandedAssessmentId(isExpanded ? null : assessment.id); },
                                    style: {color: "#8b5cf6", cursor: "pointer", fontSize: "0.85rem", fontWeight: 500},
                                  }, isExpanded ? 'Hide' : 'View Details'),
                                  (config || {}).sis_type === 'oneroster' && React.createElement('button', {
                                    key: 'sis',
                                    className: "btn btn-secondary",
                                    style: {padding: "4px 10px", fontSize: "0.78rem"},
                                    title: "Push grades and comments to SIS gradebook",
                                    onClick: function() {
                                      var scores = (assessment.submissions || []).map(function(s) {
                                        var sid = s.student_id_number || ''
                                        if (sid.startsWith('oneroster:')) sid = sid.substring('oneroster:'.length)
                                        else sid = ''
                                        return {
                                          student_sourced_id: sid,
                                          score: s.score || 0,
                                          max_score: s.total_points || (assessment.stats && assessment.stats.total_points) || 100,
                                          comment: s.feedback_summary || '',
                                        }
                                      })
                                      api.syncOneRosterGrades({
                                        assessment_id: assessment.id,
                                        title: assessment.title,
                                        total_points: (assessment.stats && assessment.stats.total_points) || 100,
                                        class_sourced_id: assessment.class_sourced_id || '',
                                        scores: scores,
                                      }).then(function(res) {
                                        if (res.error) {
                                          addToast(res.error, "error")
                                        } else {
                                          var msg = "Synced " + res.synced + " grade" + (res.synced !== 1 ? "s" : "") + " to SIS"
                                          if (res.skipped > 0) msg += ", " + res.skipped + " skipped"
                                          addToast(msg, res.failed > 0 ? "warning" : "success")
                                        }
                                      }).catch(function(err) {
                                        addToast("SIS sync error: " + err.message, "error")
                                      })
                                    },
                                  }, [React.createElement(Icon, {key: 'ic', name: "RefreshCw", size: 14}), ' Sync to SIS']),
                                  React.createElement('span', {
                                    key: 'delete',
                                    onClick: function() {
                                      if (!confirm('Delete "' + assessment.title + '" and all its submissions?')) return;
                                      api.deleteAssessment(assessment.join_code).then(function() {
                                        setAssessmentResults(function(prev) { return prev.filter(function(a) { return a.id !== assessment.id; }); });
                                      }).catch(function() {});
                                    },
                                    style: {color: "#ef4444", cursor: "pointer", fontSize: "0.8rem", opacity: 0.6},
                                  }, React.createElement(Icon, {name: "Trash2", size: 14})),
                                ]),
                              ]),

                              isExpanded && React.createElement(AssessmentDetailPanel, {
                                key: 'detail',
                                assessment: assessment,
                                assessmentStudentSort: assessmentStudentSort,
                                setAssessmentStudentSort: setAssessmentStudentSort,
                                questionBreakdownOpen: questionBreakdownOpen,
                                setQuestionBreakdownOpen: setQuestionBreakdownOpen,
                              }),
                            ]);
}
