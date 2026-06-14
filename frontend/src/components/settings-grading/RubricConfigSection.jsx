import React from "react";
import Icon from "../Icon";
import { RUBRIC_PRESETS } from "../../data/rubricPresets";

/**
 * RubricConfigSection — pure-prop rubric editor for SettingsGrading.
 * Extracted from SettingsGrading (CQ wave cq8-05 split).
 *
 * Renders the "Grading Rubric" section: category rows, Add/Reset buttons,
 * and the running weight total indicator.
 * No state, effects, or fetches — all values and handlers are props.
 */
export default function RubricConfigSection({ rubric, setRubric }) {
  const totalWeight = rubric.categories.reduce((sum, c) => sum + c.weight, 0);

  return (
    <div>
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
        <Icon
          name="ClipboardCheck"
          size={20}
          style={{ color: "#8b5cf6" }}
        />
        Grading Rubric
      </h3>
      <p
        style={{
          fontSize: "0.85rem",
          color: "var(--text-secondary)",
          marginBottom: "15px",
        }}
      >
        Configure how assignments are scored. Weights must total
        100%.
      </p>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          marginBottom: "15px",
        }}
      >
        {rubric.categories.map((cat, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: "10px",
              alignItems: "center",
              padding: "12px",
              background: "var(--input-bg)",
              borderRadius: "8px",
            }}
          >
            <input
              type="text"
              className="input"
              value={cat.name}
              onChange={(e) => {
                const updated = [...rubric.categories];
                updated[idx].name = e.target.value;
                setRubric({ ...rubric, categories: updated });
              }}
              style={{ flex: 1 }}
              placeholder="Category name"
            />
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "5px",
              }}
            >
              <input
                type="number"
                className="input"
                value={cat.weight}
                onChange={(e) => {
                  const updated = [...rubric.categories];
                  updated[idx].weight =
                    parseInt(e.target.value) || 0;
                  setRubric({ ...rubric, categories: updated });
                }}
                style={{ width: "70px", textAlign: "center" }}
                min="0"
                max="100"
              />
              <span style={{ color: "var(--text-secondary)" }}>
                %
              </span>
            </div>
            <button
              onClick={() => {
                const updated = rubric.categories.filter(
                  (_, i) => i !== idx,
                );
                setRubric({ ...rubric, categories: updated });
              }}
              style={{
                padding: "6px",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              <Icon name="X" size={16} />
            </button>
          </div>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "15px",
        }}
      >
        <button
          onClick={() => {
            setRubric({
              ...rubric,
              categories: [
                ...rubric.categories,
                { name: "", weight: 0, description: "" },
              ],
            });
          }}
          className="btn btn-secondary"
          style={{ fontSize: "0.85rem" }}
        >
          <Icon name="Plus" size={16} />
          Add Category
        </button>
        <button
          onClick={() => {
            setRubric((prev) => ({
              ...prev,
              categories: RUBRIC_PRESETS.default.categories.map((c) => ({ ...c })),
            }));
          }}
          className="btn btn-secondary"
          style={{ fontSize: "0.85rem" }}
        >
          <Icon name="RotateCcw" size={16} />
          Reset to Default
        </button>
        <span
          style={{
            fontSize: "0.85rem",
            color: totalWeight === 100 ? "#10b981" : "#ef4444",
          }}
        >
          Total:{" "}
          {totalWeight}
          %
          {totalWeight !== 100 && " (must equal 100%)"}
        </span>
      </div>
    </div>
  );
}
