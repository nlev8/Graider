import React from "react";
import Icon from "../../components/Icon";
import AssignmentTrackerCard from "./AssignmentTracker";
import AlertsGrid from "./AlertsGrid";

// API Cost Summary card — verbatim from StaticSections (CQ wave 1 split).
// Plain (non-memo) component: it was inline JSX before, so it still renders
// exactly when StaticSections renders.
function CostSummaryCard({ filteredAnalytics }) {
  if (!filteredAnalytics.cost_summary) return null;
  return (
    <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 200px" }}>
      <h3
        style={{
          fontSize: "1.1rem",
          fontWeight: 700,
          marginBottom: "15px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <Icon name="DollarSign" size={20} />
        API Cost Tracker
      </h3>
      {/* Summary stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
          gap: "12px",
          marginBottom: "20px",
        }}
      >
        {[
          { label: "Total Spend", value: "$" + filteredAnalytics.cost_summary.total_cost.toFixed(4), color: "#f59e0b" },
          { label: "Avg / Student", value: "$" + filteredAnalytics.cost_summary.avg_cost_per_student.toFixed(4), color: "#6366f1" },
          { label: "Total Tokens", value: filteredAnalytics.cost_summary.total_tokens.toLocaleString(), color: "#10b981" },
          { label: "API Calls", value: filteredAnalytics.cost_summary.total_api_calls.toLocaleString(), color: "#8b5cf6" },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              textAlign: "center",
              padding: "12px",
              background: "rgba(0,0,0,0.15)",
              borderRadius: "8px",
            }}
          >
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: stat.color }}>{stat.value}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{stat.label}</div>
          </div>
        ))}
      </div>
      {/* Cost by model */}
      {filteredAnalytics.cost_summary.by_model?.length > 0 && (
        <div style={{ marginBottom: "15px" }}>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>By Model</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {filteredAnalytics.cost_summary.by_model.map((m) => (
              <div
                key={m.model}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "var(--input-bg)",
                  borderRadius: "6px",
                  fontSize: "0.85rem",
                }}
              >
                <span style={{ fontWeight: 500 }}>{m.model}</span>
                <div style={{ display: "flex", gap: "16px", color: "var(--text-secondary)" }}>
                  <span>{m.count} graded</span>
                  <span>{m.tokens.toLocaleString()} tokens</span>
                  <span style={{ fontWeight: 600, color: "#f59e0b" }}>${m.cost.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* Cost by assignment */}
      {filteredAnalytics.cost_summary.by_assignment?.length > 0 && (
        <div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>By Assignment</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {filteredAnalytics.cost_summary.by_assignment.map((a) => (
              <div
                key={a.assignment}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "var(--input-bg)",
                  borderRadius: "6px",
                  fontSize: "0.85rem",
                }}
              >
                <span style={{ fontWeight: 500, maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.assignment}</span>
                <div style={{ display: "flex", gap: "16px", color: "var(--text-secondary)" }}>
                  <span>{a.count} students</span>
                  <span style={{ fontWeight: 600, color: "#f59e0b" }}>${a.cost.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// StaticSections — Needs Attention, Top Performers, Cost Summary, Missing Assignments
// None depend on selectedStudent, so this skips re-render on student click
const StaticSections = React.memo(function StaticSections({
  filteredAnalytics, periodStudentMap, sortedPeriods,
  savedAssignments, savedAssignmentData, config, status, addToast, periods,
  onStudentClick,
}) {

  return (
    <>
      {/* Needs Attention + Top Performers */}
      <AlertsGrid filteredAnalytics={filteredAnalytics} onStudentClick={onStudentClick} />

      {/* API Cost Summary */}
      <CostSummaryCard filteredAnalytics={filteredAnalytics} />

      {/* Missing Assignments Section */}
      <AssignmentTrackerCard
        periodStudentMap={periodStudentMap}
        sortedPeriods={sortedPeriods}
        savedAssignments={savedAssignments}
        savedAssignmentData={savedAssignmentData}
        addToast={addToast}
        periods={periods}
      />
    </>
  );
});

export default StaticSections;
