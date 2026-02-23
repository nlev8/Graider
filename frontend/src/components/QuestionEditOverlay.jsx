import { useState, useEffect } from 'react';
import Icon from './Icon';

/**
 * QuestionEditOverlay - Wraps a question card with checkbox, edit/regenerate icons, inline editing
 */
export default function QuestionEditOverlay({
  question,
  sectionIndex,
  questionIndex,
  isSelected,
  isEditing,
  isRegenerating,
  onToggleSelect,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onRegenerateOne,
  children,
}) {
  const qKey = sectionIndex + "-" + questionIndex;
  const [editData, setEditData] = useState(null);

  // Initialize edit data when entering edit mode
  useEffect(() => {
    if (isEditing) {
      setEditData(JSON.parse(JSON.stringify(question)));
    } else {
      setEditData(null);
    }
  }, [isEditing]);

  const qType = question.question_type || question.type || "short_answer";
  const isComplexType = [
    "geometry", "number_line", "coordinate_plane", "box_plot",
    "function_graph", "dot_plot", "stem_and_leaf", "bar_chart",
    "transformations", "fraction_model", "probability_tree",
    "tape_diagram", "venn_diagram", "protractor", "unit_circle",
    "data_table", "multi_part", "grid_match", "inline_dropdown",
    "multiselect",
  ].includes(qType);

  const handleSave = () => {
    if (editData) {
      onSaveEdit(sectionIndex, questionIndex, editData);
    }
  };

  return (
    <div
      style={{
        position: "relative",
        border: isSelected
          ? "2px solid rgba(99, 102, 241, 0.5)"
          : "2px solid transparent",
        borderRadius: "12px",
        background: isSelected ? "rgba(99, 102, 241, 0.05)" : "transparent",
        transition: "all 0.15s ease",
      }}
    >
      {/* Regenerating spinner overlay */}
      {isRegenerating && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            borderRadius: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "white" }}>
            <Icon name="Loader" size={20} style={{ animation: "spin 1s linear infinite" }} />
            <span>Regenerating...</span>
          </div>
        </div>
      )}

      {/* Action bar at top */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "6px 10px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Checkbox */}
        <label
          style={{ display: "flex", alignItems: "center", cursor: "pointer" }}
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(qKey)}
            style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "#6366f1" }}
          />
        </label>

        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", flex: 1 }}>
          Q{question.number || questionIndex + 1}
          {" - "}
          {(qType || "").replace(/_/g, " ")}
          {" (" + (question.points || 1) + " pt" + ((question.points || 1) > 1 ? "s" : "") + ")"}
        </span>

        {/* Edit icon */}
        {!isEditing && (
          <button
            onClick={() => onStartEdit(qKey)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              color: "var(--text-secondary)",
              borderRadius: "6px",
            }}
            title="Edit this question"
          >
            <Icon name="Pencil" size={15} />
          </button>
        )}

        {/* Single regenerate icon */}
        {!isEditing && (
          <button
            onClick={() => onRegenerateOne(sectionIndex, questionIndex)}
            disabled={isRegenerating}
            style={{
              background: "none",
              border: "none",
              cursor: isRegenerating ? "wait" : "pointer",
              padding: "4px",
              color: "var(--text-secondary)",
              borderRadius: "6px",
            }}
            title="Regenerate this question"
          >
            <Icon name="RefreshCw" size={15} />
          </button>
        )}
      </div>

      {/* Inline editing form */}
      {isEditing && editData ? (
        <div style={{ padding: "12px" }}>
          <InlineEditForm
            editData={editData}
            setEditData={setEditData}
            qType={qType}
            isComplexType={isComplexType}
            onRegenerateOne={() => onRegenerateOne(sectionIndex, questionIndex)}
          />
          <div style={{ display: "flex", gap: "8px", marginTop: "12px", justifyContent: "flex-end" }}>
            <button
              onClick={onCancelEdit}
              className="btn btn-secondary"
              style={{ padding: "6px 14px", fontSize: "0.85rem" }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="btn btn-primary"
              style={{ padding: "6px 14px", fontSize: "0.85rem" }}
            >
              <Icon name="Check" size={14} /> Save
            </button>
          </div>
        </div>
      ) : (
        /* Normal question content */
        <div style={{ padding: "4px 0" }}>
          {children}
        </div>
      )}
    </div>
  );
}


/**
 * InlineEditForm - Renders editable fields based on question type
 */
function InlineEditForm({ editData, setEditData, qType, isComplexType, onRegenerateOne }) {
  const update = (field, value) => {
    setEditData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {/* Question text - always editable */}
      <div>
        <label style={labelStyle}>Question Text</label>
        <textarea
          value={editData.question || ""}
          onChange={(e) => update("question", e.target.value)}
          rows={3}
          style={inputStyle}
        />
      </div>

      {/* Points - always editable */}
      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
        <div style={{ flex: "0 0 100px" }}>
          <label style={labelStyle}>Points</label>
          <input
            type="number"
            min={1}
            value={editData.points || 1}
            onChange={(e) => update("points", parseInt(e.target.value) || 1)}
            style={{ ...inputStyle, width: "80px" }}
          />
        </div>
      </div>

      {/* Complex types: show regenerate hint instead of structural editing */}
      {isComplexType ? (
        <div
          style={{
            padding: "12px",
            background: "rgba(245, 158, 11, 0.1)",
            border: "1px solid rgba(245, 158, 11, 0.2)",
            borderRadius: "8px",
            fontSize: "0.85rem",
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <Icon name="Info" size={16} style={{ color: "#f59e0b" }} />
          This is a complex interactive question. Edit the text/points above, or regenerate for a new version.
          <button
            onClick={onRegenerateOne}
            className="btn btn-primary"
            style={{ padding: "4px 10px", fontSize: "0.8rem", marginLeft: "auto" }}
          >
            <Icon name="RefreshCw" size={13} /> Regenerate
          </button>
        </div>
      ) : (
        <>
          {/* Multiple choice options */}
          {qType === "multiple_choice" && editData.options && (
            <div>
              <label style={labelStyle}>Options</label>
              {editData.options.map((opt, i) => (
                <div key={i} style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
                  <input
                    type="radio"
                    name="correct-option"
                    checked={editData.answer === opt || editData.correct_answer === i}
                    onChange={() => {
                      update("answer", opt);
                      update("correct_answer", i);
                    }}
                    title="Mark as correct answer"
                    style={{ accentColor: "#22c55e" }}
                  />
                  <input
                    type="text"
                    value={opt}
                    onChange={(e) => {
                      const newOpts = [...editData.options];
                      newOpts[i] = e.target.value;
                      // Update answer if this was the correct one
                      if (editData.answer === opt) {
                        update("answer", e.target.value);
                      }
                      update("options", newOpts);
                    }}
                    style={{ ...inputStyle, flex: 1 }}
                  />
                  {editData.options.length > 2 && (
                    <button
                      onClick={() => {
                        const newOpts = editData.options.filter((_, idx) => idx !== i);
                        update("options", newOpts);
                      }}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444", padding: "4px" }}
                      title="Remove option"
                    >
                      <Icon name="Minus" size={14} />
                    </button>
                  )}
                </div>
              ))}
              {editData.options.length < 6 && (
                <button
                  onClick={() => update("options", [...editData.options, "New option"])}
                  style={{
                    background: "none",
                    border: "1px dashed var(--text-muted)",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    color: "var(--text-secondary)",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <Icon name="Plus" size={13} /> Add Option
                </button>
              )}
            </div>
          )}

          {/* True/False correct answer */}
          {qType === "true_false" && (
            <div>
              <label style={labelStyle}>Correct Answer</label>
              <div style={{ display: "flex", gap: "10px" }}>
                {["True", "False"].map((val) => (
                  <label
                    key={val}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "8px 16px",
                      borderRadius: "8px",
                      cursor: "pointer",
                      background:
                        String(editData.answer).toLowerCase() === val.toLowerCase()
                          ? (val === "True" ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)")
                          : "rgba(255,255,255,0.05)",
                      border:
                        String(editData.answer).toLowerCase() === val.toLowerCase()
                          ? ("2px solid " + (val === "True" ? "#22c55e" : "#ef4444"))
                          : "2px solid var(--text-muted)",
                    }}
                  >
                    <input
                      type="radio"
                      name="tf-answer"
                      checked={String(editData.answer).toLowerCase() === val.toLowerCase()}
                      onChange={() => update("answer", val)}
                      style={{ display: "none" }}
                    />
                    {val}
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Short answer / extended response / essay */}
          {(qType === "short_answer" || qType === "extended_response" || qType === "essay" || qType === "written") && (
            <div>
              <label style={labelStyle}>Expected Answer</label>
              <textarea
                value={editData.answer || ""}
                onChange={(e) => update("answer", e.target.value)}
                rows={3}
                style={inputStyle}
              />
            </div>
          )}

          {/* Math equation */}
          {qType === "math_equation" && (
            <div>
              <label style={labelStyle}>Answer</label>
              <input
                type="text"
                value={editData.answer || ""}
                onChange={(e) => update("answer", e.target.value)}
                style={inputStyle}
              />
            </div>
          )}

          {/* Matching */}
          {qType === "matching" && editData.terms && editData.definitions && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={labelStyle}>Terms</label>
                {editData.terms.map((term, i) => (
                  <input
                    key={i}
                    type="text"
                    value={term}
                    onChange={(e) => {
                      const newTerms = [...editData.terms];
                      newTerms[i] = e.target.value;
                      update("terms", newTerms);
                    }}
                    style={{ ...inputStyle, marginBottom: "6px" }}
                  />
                ))}
              </div>
              <div>
                <label style={labelStyle}>Definitions</label>
                {editData.definitions.map((def, i) => (
                  <input
                    key={i}
                    type="text"
                    value={def}
                    onChange={(e) => {
                      const newDefs = [...editData.definitions];
                      newDefs[i] = e.target.value;
                      update("definitions", newDefs);
                    }}
                    style={{ ...inputStyle, marginBottom: "6px" }}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const labelStyle = {
  display: "block",
  fontSize: "0.8rem",
  fontWeight: 600,
  color: "var(--text-secondary)",
  marginBottom: "4px",
};

const inputStyle = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: "8px",
  border: "1px solid var(--glass-border)",
  background: "var(--input-bg, rgba(255,255,255,0.06))",
  color: "var(--text-primary)",
  fontSize: "0.9rem",
  outline: "none",
  boxSizing: "border-box",
};
