import React from "react";
import Icon from "../../components/Icon";

/*
 * AssessmentDetailPanel — extracted from AssessmentResultsSection::AssessmentRow
 * (CQ wave-4 split, #cq8-04).
 *
 * Renders the expanded detail panel for a single assessment row: the stats
 * summary cards (submissions, average, highest, lowest, avg time), the
 * student scores sortable table, and the QuestionBreakdown toggle+list.
 *
 * Pure-prop component: no useState, useEffect, or fetches. All state and
 * handlers are owned by AssessmentRow and passed down.
 */
export default function AssessmentDetailPanel({
  assessment,
  assessmentStudentSort,
  setAssessmentStudentSort,
  questionBreakdownOpen,
  setQuestionBreakdownOpen,
}) {
  var stats = assessment.stats || {};

  return React.createElement('div', {
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
      {label: 'Average', value: stats.average_score != null ? stats.average_score + '%' : '—'},
      {label: 'Highest', value: stats.highest_score != null ? stats.highest_score + '%' : '—'},
      {label: 'Lowest', value: stats.lowest_score != null ? stats.lowest_score + '%' : '—'},
      {label: 'Avg Time', value: stats.average_time_seconds ? Math.round(stats.average_time_seconds / 60) + ' min' : '—'},
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
        }, col.label + (isActive ? (assessmentStudentSort.dir === 'asc' ? ' ▲' : ' ▼') : ''));
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
            React.createElement('span', {key: 's'}, sub.score != null ? sub.score : '—'),
            React.createElement('span', {key: 'p', style: {
              fontWeight: 600,
              color: sub.percentage == null ? "var(--text-secondary)"
                : sub.percentage >= 80 ? "#22c55e"
                : sub.percentage >= 60 ? "#f59e0b" : "#ef4444",
            }}, sub.percentage != null ? sub.percentage + '%' : '—'),
            React.createElement('span', {key: 'g'}, sub.letter_grade || '—'),
            React.createElement('span', {key: 't'}, sub.time_taken_seconds ? Math.round(sub.time_taken_seconds / 60) + 'm' : '—'),
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
            qa.type + (qa.points ? ' · ' + qa.points + ' pts' : '')),
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
