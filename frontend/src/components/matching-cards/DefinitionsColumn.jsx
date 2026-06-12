import React from "react";

/**
 * DefinitionsColumn — the right (shuffled definitions) column of the
 * MatchingCards game. Stateless; extracted verbatim from MatchingCards.jsx
 * (CQ wave 8). All match state stays in the MatchingCards shell — this
 * component receives it via same-named props so `getDefStyle` and the
 * column JSX are unchanged from the original.
 */
export default function DefinitionsColumn({
  shuffledDefs,
  matched,
  selectedDef,
  shaking,
  justMatched,
  readOnly,
  handleDefClick,
}) {
  function getDefStyle(sdIdx) {
    var isUsed = Object.values(matched).indexOf(sdIdx) !== -1;
    var isSelected = selectedDef === sdIdx;
    var isShaking = shaking && shaking.def === sdIdx;
    var isJustMatched = justMatched && justMatched.def === sdIdx;

    return {
      padding: "14px 16px",
      marginBottom: "10px",
      borderRadius: "10px",
      fontSize: "0.9rem",
      cursor: readOnly || isUsed ? "default" : "pointer",
      transition: "all 0.3s ease",
      display: "flex",
      alignItems: "flex-start",
      gap: "10px",
      userSelect: "none",
      background: isJustMatched
        ? "rgba(34, 197, 94, 0.3)"
        : isUsed
        ? "rgba(34, 197, 94, 0.1)"
        : isSelected
        ? "rgba(34, 197, 94, 0.3)"
        : "rgba(34, 197, 94, 0.05)",
      border: isJustMatched
        ? "2px solid #22c55e"
        : isUsed
        ? "1px solid rgba(34, 197, 94, 0.3)"
        : isSelected
        ? "2px solid #22c55e"
        : isShaking
        ? "2px solid #ef4444"
        : "1px solid rgba(34, 197, 94, 0.15)",
      opacity: isUsed && !isJustMatched ? 0.5 : 1,
      transform: isShaking ? "translateX(4px)" : isJustMatched ? "scale(1.02)" : "none",
      animation: isShaking ? "matchShake 0.5s ease" : "none",
      textDecoration: isUsed ? "line-through" : "none",
    };
  }

  return (
    <div>
      <div style={{
        fontSize: "0.85rem",
        fontWeight: 700,
        marginBottom: "10px",
        color: "#22c55e",
        textTransform: "uppercase",
        letterSpacing: "0.5px",
      }}>
        Definitions
      </div>
      {shuffledDefs.map(function(sd, sdIdx) {
        var letter = String.fromCharCode(65 + sdIdx);
        var isUsed = Object.values(matched).indexOf(sdIdx) !== -1;
        return (
          <div
            key={sdIdx}
            onClick={function() { handleDefClick(sdIdx); }}
            style={getDefStyle(sdIdx)}
          >
            <span style={{
              minWidth: "24px",
              height: "24px",
              borderRadius: "50%",
              background: isUsed ? "#22c55e" : "rgba(34, 197, 94, 0.3)",
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: 700,
              flexShrink: 0,
            }}>
              {isUsed ? String.fromCharCode(10003) : letter}
            </span>
            <span>{sd.text}</span>
          </div>
        );
      })}
    </div>
  );
}
