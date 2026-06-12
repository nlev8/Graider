import React from "react";

/**
 * TermsColumn — the left (terms) column of the MatchingCards game.
 * Stateless; extracted verbatim from MatchingCards.jsx (CQ wave 8).
 * All match state stays in the MatchingCards shell — this component
 * receives it via same-named props so `getTermStyle` and the column
 * JSX are unchanged from the original.
 */
export default function TermsColumn({
  terms,
  matched,
  selectedTerm,
  shaking,
  justMatched,
  readOnly,
  handleTermClick,
}) {
  function getTermStyle(tIdx) {
    var isMatched = matched[tIdx] !== undefined;
    var isSelected = selectedTerm === tIdx;
    var isShaking = shaking && shaking.term === tIdx;
    var isJustMatched = justMatched && justMatched.term === tIdx;

    return {
      padding: "14px 16px",
      marginBottom: "10px",
      borderRadius: "10px",
      fontSize: "0.95rem",
      fontWeight: 600,
      cursor: readOnly || isMatched ? "default" : "pointer",
      transition: "all 0.3s ease",
      display: "flex",
      alignItems: "center",
      gap: "10px",
      userSelect: "none",
      background: isJustMatched
        ? "rgba(34, 197, 94, 0.3)"
        : isMatched
        ? "rgba(34, 197, 94, 0.1)"
        : isSelected
        ? "rgba(139, 92, 246, 0.3)"
        : "rgba(139, 92, 246, 0.08)",
      border: isJustMatched
        ? "2px solid #22c55e"
        : isMatched
        ? "1px solid rgba(34, 197, 94, 0.3)"
        : isSelected
        ? "2px solid #8b5cf6"
        : isShaking
        ? "2px solid #ef4444"
        : "1px solid rgba(139, 92, 246, 0.2)",
      opacity: isMatched && !isJustMatched ? 0.5 : 1,
      transform: isShaking ? "translateX(-4px)" : isJustMatched ? "scale(1.02)" : "none",
      animation: isShaking ? "matchShake 0.5s ease" : "none",
      textDecoration: isMatched ? "line-through" : "none",
    };
  }

  return (
    <div>
      <div style={{
        fontSize: "0.85rem",
        fontWeight: 700,
        marginBottom: "10px",
        color: "#8b5cf6",
        textTransform: "uppercase",
        letterSpacing: "0.5px",
      }}>
        Terms
      </div>
      {terms.map(function(term, tIdx) {
        return (
          <div
            key={tIdx}
            onClick={function() { handleTermClick(tIdx); }}
            style={getTermStyle(tIdx)}
          >
            <span style={{
              minWidth: "24px",
              height: "24px",
              borderRadius: "50%",
              background: matched[tIdx] !== undefined ? "#22c55e" : "#8b5cf6",
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: 700,
              flexShrink: 0,
            }}>
              {matched[tIdx] !== undefined ? String.fromCharCode(10003) : tIdx + 1}
            </span>
            <span>{term}</span>
          </div>
        );
      })}
    </div>
  );
}
