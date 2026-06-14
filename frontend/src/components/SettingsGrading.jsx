import React from "react";
import Icon from "./Icon";
import { RUBRIC_PRESETS } from "../data/rubricPresets";
import RubricConfigSection from "./settings-grading/RubricConfigSection";

export default function SettingsGrading({ config, rubric, setConfig, setRubric }) {
  return (
    <>
      <div
        data-tutorial="settings-grading"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "20px",
        }}
      >
        <div>
          <label className="label">Grading Period</label>
          <select
            className="input"
            value={config.grading_period}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                grading_period: e.target.value,
              }))
            }
          >
            <option value="Q1">Quarter 1 (Q1)</option>
            <option value="Q2">Quarter 2 (Q2)</option>
            <option value="Q3">Quarter 3 (Q3)</option>
            <option value="Q4">Quarter 4 (Q4)</option>
            <option value="S1">Semester 1 (S1)</option>
            <option value="S2">Semester 2 (S2)</option>
          </select>
        </div>
        <div>
          <label className="label">Grading Style</label>
          <select
            className="input"
            value={rubric.gradingStyle || 'standard'}
            onChange={(e) =>
              setRubric((prev) => ({
                ...prev,
                gradingStyle: e.target.value,
              }))
            }
          >
            <option value="lenient">Lenient — Reward effort and attempt</option>
            <option value="standard">Standard — Balanced grading</option>
            <option value="strict">Strict — Penalize brevity and weak answers</option>
          </select>
        </div>
      </div>

      {/* Quick Presets */}
      <div style={{ marginBottom: "20px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="Sparkles" size={20} style={{ color: "#8b5cf6" }} />
          Quick Presets
        </h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {Object.entries(RUBRIC_PRESETS)
            .filter(([key]) => {
              if (key === "default") return true;
              return config.state === "FL" && key.startsWith("FL_");
            })
            .map(([key, preset]) => (
              <button
                key={key}
                onClick={() => setRubric((prev) => ({ ...prev, categories: preset.categories.map((c) => ({ ...c })) }))}
                className="btn btn-secondary"
                style={{ fontSize: "0.8rem", padding: "6px 14px", display: "flex", alignItems: "center", gap: "6px" }}
              >
                {preset.badge && (
                  <span style={{ padding: "1px 6px", borderRadius: 4, fontSize: "0.65rem", fontWeight: 600, background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>
                    {preset.badge}
                  </span>
                )}
                {preset.name}
              </button>
            ))}
        </div>
      </div>

      {/* Rubric Configuration */}
      <RubricConfigSection rubric={rubric} setRubric={setRubric} />
    </>
  );
}
