/**
 * CurveModal — modal for applying a grade curve to all results currently
 * scoped by the period filter. Three curve types:
 *
 *   - "add"      — add N points to every score (capped at 100)
 *   - "percent"  — increase every score by N% (capped at 100)
 *   - "set_min"  — set N as the minimum score floor
 *
 * Live "75% → ..." preview reflects the chosen type + value.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `curveModal.show`. Lifted as a presentational component; App.jsx
 * still owns the underlying `curveModal` state object and the
 * `applyCurve` action.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   curveType: "add" | "percent" | "set_min"
 *   setCurveType: (val) => void
 *   curveValue: string | number
 *   setCurveValue: (val) => void
 *   periodLabel: string — name of the period filter being curved (echoed
 *                          in the "Apply a curve to all <X> results" copy)
 *   onApply: () => void — invoked when the user clicks "Apply Curve"
 */
import React from "react";
import Icon from "./Icon";

export default function CurveModal({
  open,
  onClose,
  curveType,
  setCurveType,
  curveValue,
  setCurveValue,
  periodLabel,
  onApply,
}) {
  if (!open) return null;

  const previewText = (() => {
    const val = parseFloat(curveValue) || 0;
    const example = 75;
    let newScore;
    if (curveType === "add") {
      newScore = Math.min(100, example + val);
    } else if (curveType === "percent") {
      newScore = Math.min(100, Math.round(example * (1 + val / 100)));
    } else {
      newScore = Math.max(val, example);
    }
    return `75% → ${newScore}%`;
  })();

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.7)",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
      onClick={() => onClose()}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#1a1a2e",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "400px",
          padding: "25px",
          border: "1px solid rgba(168, 85, 247, 0.3)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px",
          }}
        >
          <h2
            style={{
              fontSize: "1.2rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "10px",
              color: "#a855f7",
            }}
          >
            <Icon name="TrendingUp" size={24} />
            Apply Grade Curve
          </h2>
          <button
            onClick={() => onClose()}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "5px",
              color: "var(--text-muted)",
            }}
          >
            <Icon name="X" size={20} />
          </button>
        </div>

        <p
          style={{
            color: "var(--text-secondary)",
            marginBottom: "20px",
            fontSize: "0.9rem",
          }}
        >
          Apply a curve to all{" "}
          <span style={{ color: "#a855f7", fontWeight: 600 }}>
            {periodLabel}
          </span>{" "}
          results. This will update scores, letter grades, feedback, and emails.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
          <div>
            <label className="label">Curve Type</label>
            <select
              className="input"
              value={curveType}
              onChange={(e) => setCurveType(e.target.value)}
              style={{ width: "100%" }}
            >
              <option value="add">Add Points (e.g., +5 to every score)</option>
              <option value="percent">Percentage Boost (e.g., +10% to every score)</option>
              <option value="set_min">Set Minimum Score (e.g., min 50)</option>
            </select>
          </div>

          <div>
            <label className="label">
              {curveType === "add"
                ? "Points to Add"
                : curveType === "percent"
                  ? "Percentage Boost"
                  : "Minimum Score"}
            </label>
            <input
              type="number"
              className="input"
              value={curveValue}
              onChange={(e) => setCurveValue(e.target.value)}
              placeholder={
                curveType === "add"
                  ? "5"
                  : curveType === "percent"
                    ? "10"
                    : "50"
              }
              style={{ width: "100%" }}
            />
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "5px" }}>
              {curveType === "add"
                ? "Adds this many points to each score (capped at 100)"
                : curveType === "percent"
                  ? "Increases each score by this percentage"
                  : "Sets this as the minimum score for all results"}
            </p>
          </div>

          {/* Preview */}
          <div
            style={{
              padding: "12px",
              background: "rgba(168, 85, 247, 0.1)",
              borderRadius: "8px",
              border: "1px solid rgba(168, 85, 247, 0.2)",
            }}
          >
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "5px" }}>
              Preview (example):
            </div>
            <div style={{ fontWeight: 600 }}>
              {previewText}
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <button
              onClick={() => onClose()}
              className="btn btn-secondary"
              style={{ flex: 1 }}
            >
              Cancel
            </button>
            <button
              onClick={onApply}
              className="btn btn-primary"
              style={{
                flex: 1,
                background: "linear-gradient(135deg, #a855f7, #8b5cf6)",
              }}
            >
              <Icon name="Check" size={18} />
              Apply Curve
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
