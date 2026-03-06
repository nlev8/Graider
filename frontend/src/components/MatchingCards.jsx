import React, { useState, useMemo, useEffect } from "react";

/**
 * MatchingCards — Interactive card-matching game for vocabulary/matching questions.
 *
 * Microsoft-style: terms and definitions displayed as shuffled cards.
 * Click a term, then click the matching definition. Correct pairs disappear
 * with a success animation. Wrong pairs shake and reset.
 *
 * Props:
 *   terms: string[]         — list of terms
 *   definitions: string[]   — list of definitions (same order as terms)
 *   answerKey: string        — prefix for storing answers
 *   onMatch: (matches) => void  — called with { [termIdx]: defIdx } on each match
 *   readOnly: boolean        — if true, show all matched (for review/preview)
 *   showAnswers: boolean     — if true, show correct answers highlighted
 *   existingMatches: object  — pre-existing matches from parent state
 */
export default function MatchingCards({
  terms = [],
  definitions = [],
  onMatch,
  readOnly = false,
  showAnswers = false,
  existingMatches = {},
}) {
  // Shuffle definitions once on mount
  var shuffledDefs = useMemo(function() {
    var indexed = definitions.map(function(d, i) { return { text: d, originalIdx: i }; });
    // Fisher-Yates shuffle
    for (var i = indexed.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var temp = indexed[i];
      indexed[i] = indexed[j];
      indexed[j] = temp;
    }
    return indexed;
  }, [definitions.join("|||")]);

  var [matched, setMatched] = useState({}); // { termIdx: shuffledDefIdx }
  var [selectedTerm, setSelectedTerm] = useState(null);
  var [selectedDef, setSelectedDef] = useState(null);
  var [shaking, setShaking] = useState(null); // { term: idx, def: idx }
  var [justMatched, setJustMatched] = useState(null); // { term: idx, def: idx }

  // Initialize from existing matches
  useEffect(function() {
    if (existingMatches && Object.keys(existingMatches).length > 0) {
      setMatched(existingMatches);
    }
  }, []);

  // Show all as matched in showAnswers mode
  useEffect(function() {
    if (showAnswers && terms.length > 0) {
      var allMatched = {};
      terms.forEach(function(_, tIdx) {
        // Find the shuffled index that maps to this term's definition
        shuffledDefs.forEach(function(sd, sdIdx) {
          if (sd.originalIdx === tIdx) {
            allMatched[tIdx] = sdIdx;
          }
        });
      });
      setMatched(allMatched);
    }
  }, [showAnswers]);

  var allDone = Object.keys(matched).length === terms.length;

  function handleTermClick(tIdx) {
    if (readOnly || matched[tIdx] !== undefined) return;
    if (selectedTerm === tIdx) {
      setSelectedTerm(null);
      return;
    }
    setSelectedTerm(tIdx);

    // If a definition is already selected, try to match
    if (selectedDef !== null) {
      tryMatch(tIdx, selectedDef);
    }
  }

  function handleDefClick(sdIdx) {
    if (readOnly) return;
    // Check if this def is already matched
    var isUsed = Object.values(matched).indexOf(sdIdx) !== -1;
    if (isUsed) return;

    if (selectedDef === sdIdx) {
      setSelectedDef(null);
      return;
    }
    setSelectedDef(sdIdx);

    // If a term is already selected, try to match
    if (selectedTerm !== null) {
      tryMatch(selectedTerm, sdIdx);
    }
  }

  function tryMatch(tIdx, sdIdx) {
    var defOriginalIdx = shuffledDefs[sdIdx].originalIdx;

    if (defOriginalIdx === tIdx) {
      // Correct match!
      setJustMatched({ term: tIdx, def: sdIdx });
      setTimeout(function() {
        var newMatched = Object.assign({}, matched);
        newMatched[tIdx] = sdIdx;
        setMatched(newMatched);
        setJustMatched(null);
        setSelectedTerm(null);
        setSelectedDef(null);
        if (onMatch) {
          onMatch(newMatched);
        }
      }, 600);
    } else {
      // Wrong match — shake
      setShaking({ term: tIdx, def: sdIdx });
      setTimeout(function() {
        setShaking(null);
        setSelectedTerm(null);
        setSelectedDef(null);
      }, 500);
    }
  }

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
    <div style={{ marginTop: "12px" }}>
      {/* CSS keyframes for shake animation */}
      <style>{"\n        @keyframes matchShake {\n          0%, 100% { transform: translateX(0); }\n          20% { transform: translateX(-6px); }\n          40% { transform: translateX(6px); }\n          60% { transform: translateX(-4px); }\n          80% { transform: translateX(4px); }\n        }\n      "}</style>

      {/* Instructions */}
      {!readOnly && !allDone && (
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px", fontStyle: "italic" }}>
          Click a term, then click its matching definition. Correct pairs will disappear.
        </p>
      )}

      {/* Completion message */}
      {allDone && !readOnly && (
        <div style={{
          padding: "12px 16px",
          marginBottom: "12px",
          borderRadius: "10px",
          background: "rgba(34, 197, 94, 0.15)",
          border: "1px solid rgba(34, 197, 94, 0.3)",
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "#22c55e",
          textAlign: "center",
        }}>
          {String.fromCharCode(10003)} All terms matched correctly!
        </div>
      )}

      {/* Card grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "20px",
        padding: "15px",
        background: "rgba(0,0,0,0.08)",
        borderRadius: "12px",
      }}>
        {/* Terms column */}
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

        {/* Definitions column (shuffled) */}
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
      </div>
    </div>
  );
}
