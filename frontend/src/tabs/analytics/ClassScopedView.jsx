import React from "react";
import ProgressRankGrid from "../ProgressRankGrid";
import Gradebook from "../Gradebook";
import AssessmentComparison from "../AssessmentComparison";
import RemediationEffectiveness from "../RemediationEffectiveness";

// Class-scoped sub-tab switcher + the four class views (Progress Rank,
// Gradebook, Compare, Effectiveness). Verbatim from the AnalyticsTab render
// (CQ wave 1 split).
function ClassScopedView({ selectedClassForGrid, classView, setClassView, addToast }) {
  return (
    <div>
      {/* Sub-tab switcher (Phase 3a; Phase 4.2 #6 added 'effectiveness').
          overflow-x: auto + flex-wrap: nowrap keeps all 4 buttons on one line
          on narrow viewports per Codex round 1 brainstorm feedback. */}
      <div style={{ display: "flex", flexWrap: "nowrap", overflowX: "auto", gap: "4px", marginBottom: "12px" }}>
        <button
          onClick={function() { setClassView('progressRank'); }}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "1px solid " + (classView === 'progressRank' ? "var(--accent-primary)" : "var(--glass-border)"),
            background: classView === 'progressRank' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
            color: classView === 'progressRank' ? "var(--accent-primary)" : "var(--text-secondary)",
            fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
            whiteSpace: "nowrap", flexShrink: 0,
          }}>
          Progress Rank
        </button>
        <button
          onClick={function() { setClassView('gradebook'); }}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "1px solid " + (classView === 'gradebook' ? "var(--accent-primary)" : "var(--glass-border)"),
            background: classView === 'gradebook' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
            color: classView === 'gradebook' ? "var(--accent-primary)" : "var(--text-secondary)",
            fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
            whiteSpace: "nowrap", flexShrink: 0,
          }}>
          Gradebook
        </button>
        <button
          onClick={function() { setClassView('compare'); }}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "1px solid " + (classView === 'compare' ? "var(--accent-primary)" : "var(--glass-border)"),
            background: classView === 'compare' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
            color: classView === 'compare' ? "var(--accent-primary)" : "var(--text-secondary)",
            fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
            whiteSpace: "nowrap", flexShrink: 0,
          }}>
          Compare
        </button>
        <button
          onClick={function() { setClassView('effectiveness'); }}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "1px solid " + (classView === 'effectiveness' ? "var(--accent-primary)" : "var(--glass-border)"),
            background: classView === 'effectiveness' ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
            color: classView === 'effectiveness' ? "var(--accent-primary)" : "var(--text-secondary)",
            fontSize: "0.9rem", fontWeight: 600, cursor: "pointer",
            whiteSpace: "nowrap", flexShrink: 0,
          }}>
          Effectiveness
        </button>
      </div>
      {/* Conditional render — inactive sub-tab is unmounted so drawers can't collide.
          Phase 4.2 #6: added 'effectiveness' as the 4th branch. */}
      {classView === 'progressRank' ? (
        <ProgressRankGrid classId={selectedClassForGrid} />
      ) : classView === 'gradebook' ? (
        <Gradebook classId={selectedClassForGrid} />
      ) : classView === 'compare' ? (
        <AssessmentComparison classId={selectedClassForGrid} />
      ) : (
        <RemediationEffectiveness classId={selectedClassForGrid} addToast={addToast} />
      )}
    </div>
  );
}

export default ClassScopedView;
