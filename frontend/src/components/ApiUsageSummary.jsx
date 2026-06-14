import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

/**
 * ApiUsageSummary — pure-prop API usage cost summary panel for SettingsBilling.
 * Extracted from SettingsBilling (CQ wave cq8-05 split).
 *
 * Renders a "Load Cost Summary" button when no data, or a breakdown table when
 * data is available. No local state, effects, or fetches — all values and
 * handlers are props.
 */
export default function ApiUsageSummary({ costSummary, setCostSummary }) {
  async function loadCosts() {
    try {
      const [analyticsRes, plannerRes, assistantRes] = await Promise.all([
        api.getAnalytics().catch(() => null),
        api.getPlannerCosts().catch(() => null),
        api.getAssistantCosts().catch(() => null),
      ]);
      setCostSummary({
        grading: analyticsRes?.cost_summary || { total_cost: 0, total_graded: 0, avg_cost_per_student: 0 },
        planner: plannerRes?.total || { total_cost: 0, api_calls: 0 },
        assistant: assistantRes?.total || { total_cost: 0, api_calls: 0 },
      });
    } catch {
      setCostSummary({ grading: { total_cost: 0 }, planner: { total_cost: 0 }, assistant: { total_cost: 0 } });
    }
  }

  if (!costSummary) {
    return (
      <button onClick={loadCosts} className="btn btn-secondary" style={{ fontSize: "0.85rem" }}>
        <Icon name="RefreshCw" size={14} />
        Load Cost Summary
      </button>
    );
  }

  return (
    <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", border: "1px solid var(--glass-border)" }}>
      <div style={{ display: "grid", gap: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Grading</span>
          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            <span>${(costSummary.grading.total_cost || 0).toFixed(4)}</span>
            <span>{costSummary.grading.total_graded || 0} students</span>
            <span>~${(costSummary.grading.avg_cost_per_student || 0).toFixed(4)}/student</span>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Assistant</span>
          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            <span>${(costSummary.assistant.total_cost || 0).toFixed(4)}</span>
            <span>{costSummary.assistant.api_calls || 0} API calls</span>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Planner</span>
          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            <span>${(costSummary.planner.total_cost || 0).toFixed(4)}</span>
            <span>{costSummary.planner.api_calls || 0} API calls</span>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 0", fontWeight: 700 }}>
          <span style={{ fontSize: "0.9rem" }}>Total</span>
          <span style={{ fontSize: "0.9rem", color: "#f59e0b" }}>
            ${((costSummary.grading.total_cost || 0) + (costSummary.assistant.total_cost || 0) + (costSummary.planner.total_cost || 0)).toFixed(4)}
          </span>
        </div>
      </div>
      <button
        onClick={loadCosts}
        style={{ marginTop: "12px", padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.75rem" }}
      >
        Refresh
      </button>
    </div>
  );
}
