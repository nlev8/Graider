import React from "react";
import Icon from "../../components/Icon";

/*
 * Due Date & Late Policy panel — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split).
 */
export default function DueDatePolicySection({ assignment, setAssignment }) {
  return (
    <div style={{ marginBottom: "25px", padding: "20px", background: "var(--glass-bg)", borderRadius: "12px", border: "1px solid var(--glass-border)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
        <Icon name="Clock" size={20} style={{ color: "var(--accent-primary)" }} />
        <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>Due Date & Late Policy</h3>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "end", marginBottom: "16px" }}>
        <div>
          <label className="label">Due Date</label>
          <input
            type="datetime-local"
            className="input"
            value={assignment.dueDate}
            onChange={(e) => setAssignment({ ...assignment, dueDate: e.target.value })}
          />
        </div>
        {assignment.dueDate && (
          <button
            className="btn btn-secondary"
            onClick={() => setAssignment({ ...assignment, dueDate: "" })}
            style={{ height: "42px" }}
            title="Clear due date"
          >
            <Icon name="X" size={16} />
          </button>
        )}
      </div>
      {assignment.dueDate && (
        <>
          <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer", marginBottom: assignment.latePenalty.enabled ? "16px" : 0 }}>
            <input
              type="checkbox"
              checked={assignment.latePenalty.enabled}
              onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, enabled: e.target.checked } })}
            />
            <span style={{ fontSize: "0.9rem", fontWeight: 500 }}>Enable late penalty</span>
          </label>
          {assignment.latePenalty.enabled && (
            <div style={{ padding: "16px", background: "rgba(245,158,11,0.08)", borderRadius: "10px", border: "1px solid rgba(245,158,11,0.2)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                <div>
                  <label className="label">Penalty Type</label>
                  <select
                    className="input"
                    value={assignment.latePenalty.type}
                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, type: e.target.value } })}
                  >
                    <option value="points_per_day">Points per day</option>
                    <option value="percent_per_day">Percent per day</option>
                    <option value="tiered">Tiered brackets</option>
                  </select>
                </div>
                {assignment.latePenalty.type !== "tiered" && (
                  <div>
                    <label className="label">
                      {assignment.latePenalty.type === "points_per_day" ? "Points / day" : "% / day"}
                    </label>
                    <input
                      type="number"
                      className="input"
                      min="0"
                      value={assignment.latePenalty.amount}
                      onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, amount: parseInt(e.target.value) || 0 } })}
                    />
                  </div>
                )}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: assignment.latePenalty.type === "tiered" ? "12px" : 0 }}>
                <div>
                  <label className="label">Max Penalty {assignment.latePenalty.type === "points_per_day" ? "(pts)" : "(%)"}</label>
                  <input
                    type="number"
                    className="input"
                    min="0"
                    value={assignment.latePenalty.maxPenalty}
                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, maxPenalty: parseInt(e.target.value) || 0 } })}
                  />
                </div>
                <div>
                  <label className="label">Grace Period (hours)</label>
                  <input
                    type="number"
                    className="input"
                    min="0"
                    value={assignment.latePenalty.gracePeriodHours}
                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, gracePeriodHours: parseInt(e.target.value) || 0 } })}
                  />
                </div>
              </div>
              {assignment.latePenalty.type === "tiered" && (
                <div>
                  <label className="label">Tier Brackets</label>
                  {(assignment.latePenalty.tiers || []).map((tier, ti) => (
                    <div key={ti} style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px" }}>
                      <input
                        type="number"
                        className="input"
                        min="1"
                        value={tier.daysLate}
                        onChange={(e) => {
                          const newTiers = [...assignment.latePenalty.tiers];
                          newTiers[ti] = { ...tier, daysLate: parseInt(e.target.value) || 1 };
                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                        }}
                        style={{ width: "80px" }}
                        title="Days late"
                      />
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>days =</span>
                      <input
                        type="number"
                        className="input"
                        min="0"
                        value={tier.penalty}
                        onChange={(e) => {
                          const newTiers = [...assignment.latePenalty.tiers];
                          newTiers[ti] = { ...tier, penalty: parseInt(e.target.value) || 0 };
                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                        }}
                        style={{ width: "80px" }}
                        title="Penalty percent"
                      />
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>%</span>
                      <button
                        className="btn"
                        onClick={() => {
                          const newTiers = assignment.latePenalty.tiers.filter((_, i) => i !== ti);
                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                        }}
                        style={{ padding: "4px 8px", minWidth: 0, color: "#f87171" }}
                        title="Remove tier"
                      >
                        <Icon name="Trash2" size={14} />
                      </button>
                    </div>
                  ))}
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      const lastTier = assignment.latePenalty.tiers[assignment.latePenalty.tiers.length - 1];
                      const newDay = lastTier ? lastTier.daysLate + 2 : 1;
                      const newPenalty = lastTier ? Math.min(lastTier.penalty + 15, 100) : 10;
                      setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: [...assignment.latePenalty.tiers, { daysLate: newDay, penalty: newPenalty }] } });
                    }}
                    style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  >
                    <Icon name="Plus" size={14} /> Add Tier
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
