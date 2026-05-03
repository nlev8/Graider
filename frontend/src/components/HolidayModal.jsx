/**
 * HolidayModal — small dialog for adding a holiday or multi-day break
 * to the planner calendar. Three fields: name, start date, optional end
 * date for multi-day breaks. The Add button is disabled until name +
 * start date are both filled in.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showHolidayModal`. Presentational; the underlying `holidayForm`
 * state and `addHoliday` action remain in App.jsx.
 *
 * Props:
 *   open: bool
 *   onClose: () => void  — backdrop click + Cancel button
 *   form: { name, date, end_date }
 *   setForm: (updater) => void
 *   onAdd: (form) => void  — invoked when the user clicks Add Holiday
 *                            with both required fields filled
 */
import React from "react";
import Icon from "./Icon";

export default function HolidayModal({ open, onClose, form, setForm, onAdd }) {
  if (!open) return null;

  const canSubmit = !!(form.date && form.name);

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
      onClick={() => onClose()}
    >
      <div
        className="glass-card"
        style={{ maxWidth: "400px", width: "100%", padding: "24px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <Icon name="CalendarOff" size={20} style={{ color: "#ef4444" }} />
          Add Holiday / Break
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div>
            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="e.g., Spring Break"
              style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
            />
          </div>
          <div>
            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Start Date</label>
            <input
              type="date"
              value={form.date}
              onChange={(e) => setForm((prev) => ({ ...prev, date: e.target.value }))}
              style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
            />
          </div>
          <div>
            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>End Date (for multi-day breaks)</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => setForm((prev) => ({ ...prev, end_date: e.target.value }))}
              style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
            />
          </div>
          <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
            <button
              onClick={() => {
                if (canSubmit) {
                  onAdd(form);
                  onClose();
                }
              }}
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={!canSubmit}
            >
              Add Holiday
            </button>
            <button
              onClick={() => onClose()}
              className="btn btn-secondary"
              style={{ flex: 1 }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
