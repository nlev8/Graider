import React, { useState, useEffect, useCallback, useMemo } from "react";

/**
 * FlashcardView — Interactive flip-card component.
 * Shows one card at a time, click to flip, arrow keys to navigate, shuffle support.
 */

function getCards(data) {
  if (Array.isArray(data)) return data;
  if (data.questions) return data.questions;
  if (data.cards) return data.cards;
  return [data];
}

function getFront(item) {
  return item.question || item.front || item.term || item.text || JSON.stringify(item);
}

function getBack(item) {
  return item.answer || item.back || item.definition || item.correct_answer || "";
}

function shuffleArray(arr) {
  var copy = arr.slice();
  for (var i = copy.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var tmp = copy[i];
    copy[i] = copy[j];
    copy[j] = tmp;
  }
  return copy;
}

export default function FlashcardView({ data }) {
  var allCards = useMemo(function() { return getCards(data); }, [data]);
  var [cards, setCards] = useState(allCards);
  var [index, setIndex] = useState(0);
  var [flipped, setFlipped] = useState(false);
  var [reviewed, setReviewed] = useState({});

  // Reset when data changes
  useEffect(function() {
    setCards(allCards);
    setIndex(0);
    setFlipped(false);
    setReviewed({});
  }, [allCards]);

  var card = cards[index];
  var total = cards.length;
  var reviewedCount = Object.keys(reviewed).length;

  var goTo = useCallback(function(newIdx) {
    if (newIdx >= 0 && newIdx < total) {
      setIndex(newIdx);
      setFlipped(false);
    }
  }, [total]);

  var handleFlip = useCallback(function() {
    setFlipped(function(f) { return !f; });
    if (!flipped) {
      setReviewed(function(r) {
        var copy = Object.assign({}, r);
        copy[index] = true;
        return copy;
      });
    }
  }, [flipped, index]);

  var handleShuffle = useCallback(function() {
    setCards(shuffleArray(allCards));
    setIndex(0);
    setFlipped(false);
    setReviewed({});
  }, [allCards]);

  // Keyboard navigation
  useEffect(function() {
    function onKey(e) {
      if (e.key === "ArrowLeft") goTo(index - 1);
      else if (e.key === "ArrowRight") goTo(index + 1);
      else if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        handleFlip();
      }
    }
    window.addEventListener("keydown", onKey);
    return function() { window.removeEventListener("keydown", onKey); };
  }, [index, goTo, handleFlip]);

  if (!card) {
    return (
      <div style={{ padding: "20px", color: "var(--text-secondary)", fontStyle: "italic" }}>
        No flashcard data available.
      </div>
    );
  }

  var front = getFront(card);
  var back = getBack(card);
  var progressPct = total > 0 ? (reviewedCount / total) * 100 : 0;

  var btnStyle = {
    padding: "6px 14px", borderRadius: "8px", border: "1px solid var(--border)",
    background: "var(--bg-primary)", cursor: "pointer", fontSize: "0.85rem",
    display: "flex", alignItems: "center", gap: "4px", color: "var(--text-primary)",
  };
  var btnDisabled = Object.assign({}, btnStyle, { opacity: 0.4, cursor: "not-allowed" });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", padding: "10px 0" }}>
      {/* Card counter + shuffle */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", width: "100%", justifyContent: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
          Card {index + 1} of {total}
        </span>
        <button onClick={handleShuffle} style={btnStyle} title="Shuffle cards">
          {String.fromCharCode(8645)} Shuffle
        </button>
      </div>

      {/* Progress bar */}
      <div style={{ width: "100%", maxWidth: "420px", height: "4px", background: "var(--border)", borderRadius: "2px", overflow: "hidden" }}>
        <div style={{
          height: "100%", background: "var(--primary, #8b5cf6)", borderRadius: "2px",
          width: progressPct + "%", transition: "width 0.3s ease",
        }} />
      </div>

      {/* Flip card */}
      <div
        onClick={handleFlip}
        style={{
          width: "100%", maxWidth: "420px", minHeight: "220px",
          perspective: "800px", cursor: "pointer", userSelect: "none",
        }}
      >
        <div style={{
          position: "relative", width: "100%", minHeight: "220px",
          transformStyle: "preserve-3d",
          transition: "transform 0.5s ease",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}>
          {/* Front face */}
          <div style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            background: "var(--bg-secondary)", border: "2px solid var(--border)",
            borderRadius: "14px", padding: "24px 20px",
            display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center",
            textAlign: "center", minHeight: "220px",
          }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Question
            </div>
            <div style={{ fontSize: "1.05rem", fontWeight: 500, lineHeight: 1.5, color: "var(--text-primary)" }}>
              {front}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "16px" }}>
              Click to reveal answer
            </div>
          </div>

          {/* Back face */}
          <div style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
            background: "linear-gradient(135deg, rgba(34,197,94,0.06), rgba(34,197,94,0.02))",
            border: "2px solid rgba(34,197,94,0.3)",
            borderRadius: "14px", padding: "24px 20px",
            display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center",
            textAlign: "center", minHeight: "220px",
          }}>
            <div style={{ fontSize: "0.75rem", color: "var(--success, #22c55e)", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Answer
            </div>
            <div style={{ fontSize: "1.05rem", fontWeight: 500, lineHeight: 1.5, color: "var(--text-primary)" }}>
              {back}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "16px" }}>
              Click to flip back
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          onClick={function() { goTo(index - 1); }}
          disabled={index === 0}
          style={index === 0 ? btnDisabled : btnStyle}
        >
          {String.fromCharCode(8592)} Prev
        </button>
        <button
          onClick={function() { goTo(index + 1); }}
          disabled={index === total - 1}
          style={index === total - 1 ? btnDisabled : btnStyle}
        >
          Next {String.fromCharCode(8594)}
        </button>
      </div>

      {/* Review progress */}
      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
        {reviewedCount} of {total} reviewed {String.fromCharCode(8226)} Arrow keys to navigate {String.fromCharCode(8226)} Space to flip
      </div>
    </div>
  );
}
