import React, { useState } from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

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
                              ? (assessment.period ? assessment.period + ' \u00B7 ' : '') + 'Code: ' + assessment.join_code
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
                                  React.createElement('div', {key: 's', style: {fontSize: "0.75rem", color: "var(--text-secondary)"}}, publishDate + (subText ? ' \u00B7 ' + subText : '')),
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
                                }, stats.average_score != null ? stats.average_score + '%' : '\u2014'),
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

                              isExpanded && React.createElement('div', {
                                key: 'detail',
                                style: {
                                  padding: "20px",
                                  background: "rgba(139,92,246,0.03)",
                                  borderBottom: "1px solid var(--glass-border)",
                                },
                              }, [
                                React.createElement('div', {
                                  key: 'stats',
                                  style: {
                                    display: "flex", gap: "20px", marginBottom: "20px",
                                    flexWrap: "wrap",
                                  },
                                }, [
                                  {label: 'Submissions', value: String(stats.total_submissions || 0)},
                                  {label: 'Average', value: stats.average_score != null ? stats.average_score + '%' : '\u2014'},
                                  {label: 'Highest', value: stats.highest_score != null ? stats.highest_score + '%' : '\u2014'},
                                  {label: 'Lowest', value: stats.lowest_score != null ? stats.lowest_score + '%' : '\u2014'},
                                  {label: 'Avg Time', value: stats.average_time_seconds ? Math.round(stats.average_time_seconds / 60) + ' min' : '\u2014'},
                                ].map(function(s) {
                                  return React.createElement('div', {key: s.label, style: {
                                    padding: "10px 16px", background: "var(--glass-bg)", borderRadius: "8px",
                                    border: "1px solid var(--glass-border)", textAlign: "center", minWidth: "80px",
                                  }}, [
                                    React.createElement('div', {key: 'v', style: {fontWeight: 700, fontSize: "1.1rem"}}, s.value),
                                    React.createElement('div', {key: 'l', style: {fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: "2px"}}, s.label),
                                  ]);
                                })),

                                React.createElement('div', {key: 'students', style: {marginBottom: "16px"}}, [
                                  React.createElement('div', {key: 'hdr', style: {fontWeight: 600, marginBottom: "8px", fontSize: "0.9rem"}}, 'Student Scores'),
                                  React.createElement('div', {key: 'thead', style: {
                                    display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                                    padding: "8px 12px", fontSize: "0.7rem", color: "var(--text-secondary)",
                                    fontWeight: 600, textTransform: "uppercase", borderBottom: "1px solid var(--glass-border)",
                                  }}, [
                                    {key: 'n', field: 'student_name', label: 'Student'},
                                    {key: 's', field: 'score', label: 'Score'},
                                    {key: 'p', field: 'percentage', label: 'Percentage'},
                                    {key: 'g', field: 'letter_grade', label: 'Grade'},
                                    {key: 't', field: 'time_taken_seconds', label: 'Time'},
                                    {key: 'st', field: 'status', label: 'Status'},
                                  ].map(function(col) {
                                    var isActive = assessmentStudentSort.field === col.field;
                                    return React.createElement('span', {
                                      key: col.key,
                                      onClick: function() {
                                        setAssessmentStudentSort({
                                          field: col.field,
                                          dir: isActive && assessmentStudentSort.dir === 'asc' ? 'desc' : 'asc',
                                        });
                                      },
                                      style: {cursor: "pointer", color: isActive ? "#8b5cf6" : "var(--text-secondary)"},
                                    }, col.label + (isActive ? (assessmentStudentSort.dir === 'asc' ? ' \u25B2' : ' \u25BC') : ''));
                                  })),
                                  ...(assessment.submissions || [])
                                    .sort(function(a, b) {
                                      var field = assessmentStudentSort.field;
                                      var dir = assessmentStudentSort.dir === 'asc' ? 1 : -1;
                                      var va = a[field] || '';
                                      var vb = b[field] || '';
                                      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
                                      return String(va).localeCompare(String(vb)) * dir;
                                    })
                                    .map(function(sub, si) {
                                      return React.createElement('div', {
                                        key: si,
                                        style: {
                                          display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                                          padding: "8px 12px", fontSize: "0.85rem",
                                          borderBottom: "1px solid rgba(255,255,255,0.05)",
                                        },
                                      }, [
                                        React.createElement('span', {key: 'n'}, sub.student_name),
                                        React.createElement('span', {key: 's'}, sub.score != null ? sub.score : '\u2014'),
                                        React.createElement('span', {key: 'p', style: {
                                          fontWeight: 600,
                                          color: sub.percentage == null ? "var(--text-secondary)"
                                            : sub.percentage >= 80 ? "#22c55e"
                                            : sub.percentage >= 60 ? "#f59e0b" : "#ef4444",
                                        }}, sub.percentage != null ? sub.percentage + '%' : '\u2014'),
                                        React.createElement('span', {key: 'g'}, sub.letter_grade || '\u2014'),
                                        React.createElement('span', {key: 't'}, sub.time_taken_seconds ? Math.round(sub.time_taken_seconds / 60) + 'm' : '\u2014'),
                                        React.createElement('span', {key: 'st', style: {
                                          color: sub.status === 'graded' ? "#22c55e" : sub.status === 'pending' ? "#f59e0b" : "var(--text-secondary)",
                                        }}, sub.status || 'submitted'),
                                      ]);
                                    }),
                                ]),
                                React.createElement(QuestionBreakdown, {
                                  key: 'qbreakdown',
                                  assessment: assessment,
                                  questionBreakdownOpen: questionBreakdownOpen,
                                  setQuestionBreakdownOpen: setQuestionBreakdownOpen,
                                }),
                              ]),
                            ]);
}

function QuestionBreakdown({
  assessment,
  questionBreakdownOpen,
  setQuestionBreakdownOpen,
}) {
  return React.createElement('div', {key: 'qbreakdown'}, [
                                  React.createElement('div', {
                                    key: 'toggle',
                                    onClick: function() { setQuestionBreakdownOpen(!questionBreakdownOpen); },
                                    style: {
                                      display: "flex", alignItems: "center", gap: "8px",
                                      cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", marginBottom: "8px",
                                    },
                                  }, [
                                    React.createElement(Icon, {key: 'ic', name: questionBreakdownOpen ? "ChevronDown" : "ChevronRight", size: 14}),
                                    React.createElement('span', {key: 'txt'}, 'Per-Question Breakdown'),
                                  ]),
                                  questionBreakdownOpen && React.createElement('div', {key: 'questions'},
                                    (assessment.question_analysis || []).map(function(qa, qi) {
                                      var isLow = qa.percent_correct !== null && qa.percent_correct < 50;
                                      return React.createElement('div', {
                                        key: qi,
                                        style: {
                                          padding: "10px 12px", marginBottom: "6px",
                                          background: isLow ? "rgba(239,68,68,0.08)" : "var(--glass-bg)",
                                          border: "1px solid " + (isLow ? "rgba(239,68,68,0.2)" : "var(--glass-border)"),
                                          borderRadius: "8px",
                                        },
                                      }, [
                                        React.createElement('div', {key: 'hd', style: {display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px"}}, [
                                          React.createElement('span', {key: 'q', style: {fontWeight: 600, fontSize: "0.85rem"}},
                                            'Q' + qa.number + ': ' + (qa.question || '').substring(0, 80) + (qa.question && qa.question.length > 80 ? '...' : '')),
                                          React.createElement('span', {key: 'pct', style: {
                                            fontSize: "0.8rem", fontWeight: 600,
                                            color: qa.percent_correct == null ? "var(--text-secondary)"
                                              : qa.percent_correct >= 80 ? "#22c55e"
                                              : qa.percent_correct >= 50 ? "#f59e0b" : "#ef4444",
                                          }}, qa.percent_correct != null ? qa.percent_correct + '% correct' : (qa.graded_count != null ? qa.graded_count + ' graded' : '')),
                                        ]),
                                        React.createElement('div', {key: 'meta', style: {fontSize: "0.75rem", color: "var(--text-secondary)"}},
                                          qa.type + (qa.points ? ' \u00B7 ' + qa.points + ' pts' : '')),
                                        qa.response_distribution && React.createElement('div', {key: 'dist', style: {marginTop: "6px"}},
                                          Object.keys(qa.response_distribution).map(function(opt) {
                                            var d = qa.response_distribution[opt];
                                            return React.createElement('div', {
                                              key: opt,
                                              style: {display: "flex", alignItems: "center", gap: "8px", marginBottom: "3px", fontSize: "0.8rem"},
                                            }, [
                                              React.createElement('span', {key: 'lbl', style: {width: "30px", fontWeight: d.is_correct ? 700 : 400}}, opt),
                                              React.createElement('div', {key: 'bar', style: {
                                                flex: 1, height: "14px", background: "rgba(255,255,255,0.06)", borderRadius: "4px", overflow: "hidden",
                                              }}, React.createElement('div', {style: {
                                                width: (d.percent || 0) + '%', height: "100%",
                                                background: d.is_correct ? "#22c55e" : "rgba(139,92,246,0.4)",
                                                borderRadius: "4px",
                                              }})),
                                              React.createElement('span', {key: 'cnt', style: {width: "60px", textAlign: "right", fontSize: "0.75rem"}},
                                                d.count + ' (' + d.percent + '%)'),
                                              d.is_correct && React.createElement(Icon, {key: 'chk', name: "Check", size: 12, color: "#22c55e"}),
                                            ]);
                                          })
                                        ),
                                        qa.graded_count != null && !qa.response_distribution && React.createElement('div', {
                                          key: 'sa', style: {marginTop: "6px", fontSize: "0.8rem", color: "var(--text-secondary)"},
                                        }, 'Graded: ' + qa.graded_count + ' | Pending: ' + (qa.pending_count || 0) + (qa.average_score != null ? ' | Avg: ' + qa.average_score + '/' + qa.max_points : '')),
                                      ]);
                                    })
                                  ),
  ]);
}
