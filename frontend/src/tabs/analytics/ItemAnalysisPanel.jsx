import React from "react";
import Icon from "../../components/Icon";

// Item Analysis panel — verbatim from the AnalyticsTab render (CQ wave 1
// split). The open/selection state stays in AnalyticsTab so persistence
// semantics across assessmentResults changes are unchanged.
function ItemAnalysisPanel({
  assessmentResults, selectedItemAnalysis, setSelectedItemAnalysis,
  itemAnalysisOpen, setItemAnalysisOpen,
}) {
  if (!assessmentResults || assessmentResults.length === 0) return null;
  return (
    <div style={{
      padding: "16px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
      borderRadius: "12px", marginBottom: "16px",
    }}>
      <div
        onClick={function() { setItemAnalysisOpen(function(p) { return !p; }); }}
        style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: itemAnalysisOpen ? "12px" : "0", display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", userSelect: "none" }}
      >
        <Icon name={itemAnalysisOpen ? "ChevronDown" : "ChevronRight"} size={16} />
        <Icon name="ClipboardList" size={16} />
        Item Analysis
        <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 400, marginLeft: "auto" }}>
          {itemAnalysisOpen ? "click to collapse" : "click to expand"}
        </span>
      </div>
      {itemAnalysisOpen && (<><select
        value={selectedItemAnalysis || ''}
        onChange={function(e) { setSelectedItemAnalysis(e.target.value); }}
        style={{
          width: "100%", padding: "8px 12px", borderRadius: "8px",
          border: "1px solid var(--glass-border)", background: "var(--surface)",
          color: "var(--text-primary)", fontSize: "0.85rem", marginBottom: "12px",
        }}
      >
        {assessmentResults.map(function(a) {
          return React.createElement('option', {key: a.id, value: a.id}, a.title + ' (' + (a.assessment_category || 'formative') + ')');
        })}
      </select>
      {(function() {
        var selected = assessmentResults.find(function(a) { return a.id === (selectedItemAnalysis || (assessmentResults[0] && assessmentResults[0].id)); });
        if (!selected || !selected.question_analysis) return null;
        return selected.question_analysis.map(function(qa, qi) {
          var pct = qa.percent_correct;
          var barColor = pct == null ? '#6b7280' : pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444';
          return React.createElement('div', {
            key: qi,
            style: { marginBottom: "8px" },
          }, [
            React.createElement('div', {key: 'label', style: {display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "3px"}}, [
              React.createElement('span', {key: 'q'}, 'Q' + qa.number + ' (' + qa.type + ')'),
              React.createElement('span', {key: 'p', style: {fontWeight: 600, color: barColor}},
                pct != null ? pct + '%' : (qa.graded_count != null ? qa.graded_count + ' graded' : 'N/A')),
            ]),
            pct != null && React.createElement('div', {key: 'bar', style: {
              width: "100%", height: "16px", background: "rgba(255,255,255,0.06)", borderRadius: "4px", overflow: "hidden",
            }}, React.createElement('div', {style: {
              width: pct + '%', height: "100%", background: barColor, borderRadius: "4px",
              transition: "width 0.3s ease",
            }})),
            qa.response_distribution && React.createElement('div', {key: 'dist', style: {marginTop: "4px", paddingLeft: "8px"}},
              Object.keys(qa.response_distribution).map(function(opt) {
                var d = qa.response_distribution[opt];
                return React.createElement('div', {key: opt, style: {
                  display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", marginBottom: "2px",
                }}, [
                  React.createElement('span', {key: 'l', style: {width: "24px", fontWeight: d.is_correct ? 700 : 400}}, opt),
                  React.createElement('span', {key: 'c'}, d.count + ' (' + d.percent + '%)'),
                  d.is_correct && React.createElement(Icon, {key: 'chk', name: "Check", size: 10, color: "#22c55e"}),
                ]);
              })
            ),
            qa.graded_count != null && !qa.response_distribution && React.createElement('div', {
              key: 'sa', style: {fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px"},
            }, 'Graded: ' + qa.graded_count + ' | Pending: ' + (qa.pending_count || 0) + (qa.average_score != null ? ' | Avg: ' + qa.average_score + '/' + qa.max_points : '')),
          ]);
        });
      })()}
      </>)}
    </div>
  );
}

export default ItemAnalysisPanel;
