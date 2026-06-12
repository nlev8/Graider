/**
 * StandardCardDetails — the expandable details panel of a StandardCard
 * (essential questions, learning targets, vocabulary, item specs, sample
 * assessment). Stateless; extracted verbatim from StandardCard.jsx (CQ
 * wave 8). The shell's `{isExpanded && ...}` guard moved here as an
 * early-return-null.
 */
import React from "react";
import Icon from "../Icon";

export default function StandardCardDetails({ standard, isExpanded }) {
  if (!isExpanded) return null;
  return (
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
  );
}
