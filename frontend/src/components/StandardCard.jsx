/**
 * StandardCard — renders a single curriculum standard with optional
 * expandable details (essential questions, learning targets, vocabulary,
 * item specs, sample assessment).
 *
 * Extracted from App.jsx + PlannerTab.jsx (2026-05-02) where it was
 * duplicated. The two copies were near-identical (only minor cosmetic
 * differences: comment lines + bullet glyph form). The App.jsx version
 * is canonical here.
 *
 * Props:
 *   standard: object with code, benchmark, dok, topics, learning_targets,
 *             vocabulary, essential_questions, item_specs, sample_assessment
 *   isSelected: bool
 *   onToggle: () => void — called on row click (selection toggle)
 *   isExpanded: bool — show/hide details panel
 *   onExpand: () => void — called when expand button clicked
 */
import React from "react";
import Icon from "./Icon";

export default function StandardCard({
  standard,
  isSelected,
  onToggle,
  isExpanded,
  onExpand,
}) {
  const dokColors = { 1: "#4ade80", 2: "#60a5fa", 3: "#f59e0b", 4: "#ef4444" };
  const dokLabels = {
    1: "Recall",
    2: "Skill/Concept",
    3: "Strategic Thinking",
    4: "Extended Thinking",
  };

  return (
    <div
      style={{
        background: isSelected ? "rgba(99,102,241,0.2)" : "var(--glass-bg)",
        border: isSelected
          ? "1px solid var(--accent-primary)"
          : "1px solid var(--glass-border)",
        borderRadius: "12px",
        padding: "15px",
        transition: "all 0.2s",
        marginBottom: "10px",
      }}
    >
      <div onClick={onToggle} style={{ cursor: "pointer" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                fontWeight: 700,
                color: isSelected
                  ? "var(--accent-light)"
                  : "var(--text-primary)",
                fontSize: "0.9rem",
              }}
            >
              {standard.code}
            </span>
            {standard.dok && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  borderRadius: "10px",
                  background: dokColors[standard.dok] + "33",
                  color: dokColors[standard.dok],
                  fontWeight: 600,
                }}
                title={`Depth of Knowledge: ${dokLabels[standard.dok]}`}
              >
                DOK {standard.dok}
              </span>
            )}
          </div>
          {isSelected && (
            <Icon
              name="CheckCircle"
              size={18}
              style={{ color: "var(--accent-primary)" }}
            />
          )}
        </div>
        <p
          style={{
            fontSize: "0.9rem",
            color: "var(--text-secondary)",
            lineHeight: "1.5",
            margin: "0 0 10px 0",
          }}
        >
          {standard.benchmark}
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
            alignItems: "center",
          }}
        >
          {(standard.topics || []).map((topic) => (
            <span
              key={topic}
              style={{
                fontSize: "0.75rem",
                padding: "3px 8px",
                borderRadius: "4px",
                background: "var(--glass-hover)",
                color: "var(--text-secondary)",
              }}
            >
              {topic}
            </span>
          ))}
        </div>
      </div>

      {(standard.learning_targets ||
        standard.vocabulary ||
        standard.essential_questions) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onExpand && onExpand();
          }}
          style={{
            marginTop: "10px",
            padding: "4px 10px",
            fontSize: "0.75rem",
            background: "transparent",
            border: "1px solid var(--glass-border)",
            borderRadius: "6px",
            color: "var(--text-secondary)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <Icon name={isExpanded ? "ChevronUp" : "ChevronDown"} size={14} />
          {isExpanded ? "Hide Details" : "Show Details"}
        </button>
      )}

      {isExpanded && (
        <div
          style={{
            marginTop: "15px",
            paddingTop: "15px",
            borderTop: "1px solid var(--glass-border)",
          }}
        >
          {standard.essential_questions &&
            standard.essential_questions.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "#8b5cf6",
                    marginBottom: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Icon name="HelpCircle" size={14} /> Essential Questions
                </div>
                {standard.essential_questions.map((q, i) => (
                  <p
                    key={i}
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      margin: "4px 0",
                      paddingLeft: "20px",
                    }}
                  >
                    {'\u2022'} {q}
                  </p>
                ))}
              </div>
            )}

          {standard.learning_targets &&
            standard.learning_targets.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "#10b981",
                    marginBottom: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Icon name="Target" size={14} /> Learning Targets
                </div>
                {standard.learning_targets.map((t, i) => (
                  <p
                    key={i}
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      margin: "4px 0",
                      paddingLeft: "20px",
                    }}
                  >
                    {'\u2022'} {t}
                  </p>
                ))}
              </div>
            )}

          {standard.vocabulary && standard.vocabulary.length > 0 && (
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#f59e0b",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="BookOpen" size={14} /> Key Vocabulary
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                  paddingLeft: "20px",
                }}
              >
                {standard.vocabulary.map((v, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: "0.8rem",
                      padding: "3px 10px",
                      borderRadius: "12px",
                      background: "rgba(245,158,11,0.15)",
                      color: "#f59e0b",
                    }}
                  >
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {standard.item_specs && (
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#6366f1",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="ClipboardList" size={14} /> Item Specifications
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  margin: "0",
                  paddingLeft: "20px",
                }}
              >
                {standard.item_specs}
              </p>
            </div>
          )}

          {standard.sample_assessment && (
            <div>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#ec4899",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="FileQuestion" size={14} /> Sample Assessment Item
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  margin: "0",
                  paddingLeft: "20px",
                  fontStyle: "italic",
                  background: "var(--glass-hover)",
                  padding: "10px",
                  borderRadius: "8px",
                }}
              >
                {standard.sample_assessment}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
