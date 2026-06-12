import React from "react";
import Icon from "../../components/Icon";

/*
 * Assignment Rubric selector + preview + custom-rubric editor — relocated
 * verbatim from BuilderTab.jsx (CQ wave-9 split).
 */
export default function RubricTypeSection({ assignment, setAssignment }) {
  return (
    <div data-tutorial="builder-rubric" style={{ marginBottom: "25px" }}>
      <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Icon name="Scale" size={16} style={{ color: "#8b5cf6" }} />
        Assignment Rubric
      </label>
      <select
        className="input"
        value={assignment.rubricType || "standard"}
        onChange={(e) => {
          const newType = e.target.value;
          setAssignment({
            ...assignment,
            rubricType: newType,
            // Auto-set grading notes for fill-in-blank if not already set
            gradingNotes: newType === "fill-in-blank" && !assignment.gradingNotes
              ? "This is a Fill-in-the-Blank activity. Grade on accuracy and completion only."
              : assignment.gradingNotes,
          });
        }}
        style={{ marginBottom: "10px" }}
      >
        <option value="standard">Standard (Use Global Rubric)</option>
        <option value="fill-in-blank">Fill-in-the-Blank (Accuracy + Completion)</option>
        <option value="essay">Essay/Written Response (Writing Quality Focus)</option>
        <option value="cornell-notes">Cornell Notes (Structure + Summary)</option>
        <option value="completion-only">Completion Only (No AI Grading)</option>
        <option value="custom">Custom Rubric...</option>
      </select>

      {/* Rubric Preview/Description */}
      {assignment.rubricType && assignment.rubricType !== "standard" && assignment.rubricType !== "custom" && (
        <div style={{
          padding: "12px",
          background: "rgba(139, 92, 246, 0.1)",
          borderRadius: "8px",
          fontSize: "0.85rem",
          color: "var(--text-secondary)",
          marginBottom: "10px",
        }}>
          {assignment.rubricType === "fill-in-blank" && (
            <div><strong>Categories:</strong> Accuracy (70%) + Completion (30%)<br/>Spelling errors ignored if intent is clear.</div>
          )}
          {assignment.rubricType === "essay" && (
            <div><strong>Categories:</strong> Content (35%) + Writing Quality (30%) + Analysis (20%) + Effort (15%)</div>
          )}
          {assignment.rubricType === "cornell-notes" && (
            <div><strong>Categories:</strong> Content (40%) + Note Structure (25%) + Summary (20%) + Effort (15%)</div>
          )}
          {assignment.rubricType === "completion-only" && (
            <div><strong>No AI grading.</strong> Just tracks that the assignment was submitted.</div>
          )}
        </div>
      )}

      {/* Custom Rubric Editor */}
      {assignment.rubricType === "custom" && (
        <div style={{
          padding: "15px",
          background: "rgba(139, 92, 246, 0.08)",
          borderRadius: "10px",
          border: "1px solid rgba(139, 92, 246, 0.2)",
        }}>
          <div style={{ fontWeight: 600, marginBottom: "12px", fontSize: "0.9rem" }}>
            Custom Rubric Categories
          </div>
          {(assignment.customRubric || [
            { name: "Content Accuracy", weight: 40 },
            { name: "Completeness", weight: 25 },
            { name: "Writing Quality", weight: 20 },
            { name: "Effort", weight: 15 },
          ]).map((cat, i) => (
            <div key={i} style={{ display: "flex", gap: "10px", marginBottom: "8px", alignItems: "center" }}>
              <input
                className="input"
                value={cat.name}
                onChange={(e) => {
                  const newRubric = [...(assignment.customRubric || [
                    { name: "Content Accuracy", weight: 40 },
                    { name: "Completeness", weight: 25 },
                    { name: "Writing Quality", weight: 20 },
                    { name: "Effort", weight: 15 },
                  ])];
                  newRubric[i] = { ...newRubric[i], name: e.target.value };
                  setAssignment({ ...assignment, customRubric: newRubric });
                }}
                placeholder="Category name"
                style={{ flex: 1 }}
              />
              <input
                className="input"
                type="number"
                value={cat.weight}
                onChange={(e) => {
                  const newRubric = [...(assignment.customRubric || [
                    { name: "Content Accuracy", weight: 40 },
                    { name: "Completeness", weight: 25 },
                    { name: "Writing Quality", weight: 20 },
                    { name: "Effort", weight: 15 },
                  ])];
                  newRubric[i] = { ...newRubric[i], weight: parseInt(e.target.value) || 0 };
                  setAssignment({ ...assignment, customRubric: newRubric });
                }}
                style={{ width: "70px" }}
                min="0"
                max="100"
              />
              <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>%</span>
              <button
                onClick={() => {
                  const newRubric = (assignment.customRubric || [
                    { name: "Content Accuracy", weight: 40 },
                    { name: "Completeness", weight: 25 },
                    { name: "Writing Quality", weight: 20 },
                    { name: "Effort", weight: 15 },
                  ]).filter((_, idx) => idx !== i);
                  setAssignment({ ...assignment, customRubric: newRubric });
                }}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
              >
                <Icon name="X" size={16} />
              </button>
            </div>
          ))}
          <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
          <button
            onClick={() => {
              const newRubric = [...(assignment.customRubric || [
                { name: "Content Accuracy", weight: 40 },
                { name: "Completeness", weight: 25 },
                { name: "Writing Quality", weight: 20 },
                { name: "Effort", weight: 15 },
              ]), { name: "", weight: 0 }];
              setAssignment({ ...assignment, customRubric: newRubric });
            }}
            className="btn btn-secondary"
            style={{ fontSize: "0.85rem" }}
          >
            <Icon name="Plus" size={14} /> Add Category
          </button>
          <button
            onClick={() => {
              setAssignment({ ...assignment, customRubric: [
                { name: "Content Accuracy", weight: 40 },
                { name: "Completeness", weight: 25 },
                { name: "Writing Quality", weight: 20 },
                { name: "Effort", weight: 15 },
              ]});
            }}
            className="btn btn-secondary"
            style={{ fontSize: "0.85rem" }}
          >
            <Icon name="RotateCcw" size={14} /> Reset to Default
          </button>
          </div>
          <div style={{ marginTop: "10px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Total: {(assignment.customRubric || [
              { name: "Content Accuracy", weight: 40 },
              { name: "Completeness", weight: 25 },
              { name: "Writing Quality", weight: 20 },
              { name: "Effort", weight: 15 },
            ]).reduce((sum, c) => sum + (c.weight || 0), 0)}%
            {(assignment.customRubric || []).reduce((sum, c) => sum + (c.weight || 0), 0) !== 100 && (
              <span style={{ color: "#f59e0b" }}> (should be 100%)</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
