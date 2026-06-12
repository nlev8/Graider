import React, { useState, useMemo, useEffect } from "react";
import TermsColumn from "./matching-cards/TermsColumn";
import DefinitionsColumn from "./matching-cards/DefinitionsColumn";

/**
 * MatchingCards — Interactive card-matching game for vocabulary/matching questions.
 *
 * Microsoft-style: terms and definitions displayed as shuffled cards.
 * Click a term, then click the matching definition. Correct pairs disappear
 * with a success animation. Wrong pairs shake and reset.
 *
 * Shell owns ALL match state (matched/selectedTerm/selectedDef/shaking/
 * justMatched), the shuffle + correct-answer memos, the click handlers, and
 * tryMatch — unchanged from before the CQ wave 8 split. The two card columns
 * (with their per-card style builders) are stateless children in
 * matching-cards/, receiving the shell's state via same-named props.
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
  correctAnswer = null,
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
        // Find the shuffled index that maps to this term's correct definition
        var expectedDefIdx = correctDefForTerm[tIdx];
        shuffledDefs.forEach(function(sd, sdIdx) {
          if (sd.originalIdx === expectedDefIdx) {
            allMatched[tIdx] = sdIdx;
          }
        });
      });
      setMatched(allMatched);
    }
  }, [showAnswers, correctDefForTerm]);

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

  // Build a lookup: for each term, which original definition index is correct?
  var correctDefForTerm = useMemo(function() {
    var lookup = {};
    if (correctAnswer && typeof correctAnswer === "object" && !Array.isArray(correctAnswer)) {
      // Dict format: { "Term": "B" } or { "Term": "definition text" }
      terms.forEach(function(term, tIdx) {
        var val = correctAnswer[term];
        if (!val) return;
        // If value is a single letter like "A", "B", map to definition index
        if (val.length === 1 && val >= "A" && val <= "Z") {
          lookup[tIdx] = val.charCodeAt(0) - 65;
        } else {
          // Value is the definition text — find its index
          definitions.forEach(function(d, dIdx) {
            if (d === val || d.replace(/^[A-Z]\)\s*/, "") === val) {
              lookup[tIdx] = dIdx;
            }
          });
        }
      });
    } else if (Array.isArray(correctAnswer) && correctAnswer.length > 0 && typeof correctAnswer[0] === 'number') {
      // Integer array format: [0, 1, 2, 3] — terms[i] matches definitions[correctAnswer[i]]
      correctAnswer.forEach(function(defIdx, tIdx) {
        if (typeof defIdx === 'number' && defIdx >= 0 && defIdx < definitions.length) {
          lookup[tIdx] = defIdx;
        }
      });
    } else if (Array.isArray(correctAnswer)) {
      // Array format: ["Term: definition", "Term - definition"]
      correctAnswer.forEach(function(entry) {
        // Split on first colon or " - " only, to avoid breaking definitions containing colons/hyphens
        var sepIdx = entry.indexOf(": ");
        if (sepIdx === -1) sepIdx = entry.indexOf(" - ");
        if (sepIdx === -1) sepIdx = entry.indexOf(":");
        if (sepIdx === -1) return;
        var answerTerm = entry.substring(0, sepIdx).trim();
        var answerDef = entry.substring(sepIdx + (entry.charAt(sepIdx + 1) === " " ? 2 : 1)).trim();
        if (answerTerm && answerDef) {
          var tIdx = terms.indexOf(answerTerm);
          if (tIdx === -1) {
            // Try case-insensitive
            terms.forEach(function(t, i) {
              if (t.toLowerCase() === answerTerm.toLowerCase()) tIdx = i;
            });
          }
          if (tIdx !== -1) {
            definitions.forEach(function(d, dIdx) {
              if (d === answerDef || d.startsWith(answerDef.substring(0, 30))) {
                lookup[tIdx] = dIdx;
              }
            });
          }
        }
      });
    }
    // Fallback: if no correctAnswer provided, assume terms[i] matches definitions[i]
    if (Object.keys(lookup).length === 0) {
      terms.forEach(function(_, i) { lookup[i] = i; });
    }
    return lookup;
  }, [terms.join("|||"), definitions.join("|||"), JSON.stringify(correctAnswer)]);

  function tryMatch(tIdx, sdIdx) {
    var defOriginalIdx = shuffledDefs[sdIdx].originalIdx;
    var expectedDefIdx = correctDefForTerm[tIdx];
    if (defOriginalIdx === expectedDefIdx) {
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
          onMatch(newMatched, shuffledDefs);
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
        <TermsColumn
          terms={terms}
          matched={matched}
          selectedTerm={selectedTerm}
          shaking={shaking}
          justMatched={justMatched}
          readOnly={readOnly}
          handleTermClick={handleTermClick}
        />

        {/* Definitions column (shuffled) */}
        <DefinitionsColumn
          shuffledDefs={shuffledDefs}
          matched={matched}
          selectedDef={selectedDef}
          shaking={shaking}
          justMatched={justMatched}
          readOnly={readOnly}
          handleDefClick={handleDefClick}
        />
      </div>
    </div>
  );
}
