import React, { useEffect } from "react";
import Icon from "./Icon";

/**
 * QuestionFeedback — Overlay shown after answering MC/TF on assignments.
 * Shows checkmark/X, points earned, streak count. Auto-advances after 1.5s.
 *
 * Props:
 *   isCorrect: boolean
 *   points: number — points earned (0 if wrong)
 *   maxPoints: number — max points for this question
 *   streak: number — consecutive correct answers
 *   onNext: () => void — callback to advance
 */
export default function QuestionFeedback({ isCorrect, points, maxPoints, streak, onNext, hideStreak }) {
  useEffect(function() {
    var timer = setTimeout(onNext, 1500);
    return function() { clearTimeout(timer); };
  }, [onNext]);

  return (
    <div
      onClick={onNext}
      style={{
        position: "fixed",
        top: 0, left: 0, right: 0, bottom: 0,
        background: "rgba(0, 0, 0, 0.85)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        cursor: "pointer",
      }}
    >
      {/* Checkmark or X */}
      <div style={{
        marginBottom: "10px",
        color: isCorrect ? "#22c55e" : "#ef4444",
      }}>
        <Icon name={isCorrect ? "CheckCircle" : "XCircle"} size={80} />
      </div>

      {/* Correct/Incorrect + Points */}
      <div style={{
        fontSize: "1.8rem",
        fontWeight: 700,
        color: isCorrect ? "#22c55e" : "#ef4444",
        marginBottom: "8px",
      }}>
        {isCorrect ? "Correct!" : "Incorrect"}
      </div>
      <div style={{
        fontSize: "1.2rem",
        color: "rgba(255,255,255,0.7)",
        marginBottom: "20px",
      }}>
        {isCorrect ? "+" + points + " point" + (points !== 1 ? "s" : "") : "0/" + maxPoints + " points"}
      </div>

      {/* Streak indicator */}
      {isCorrect && streak > 1 && !hideStreak && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ display: "flex", gap: "6px" }}>
            {Array.from({ length: Math.min(streak, 10) }).map(function(_, i) {
              return <div key={i} style={{
                width: "10px", height: "10px", borderRadius: "50%", background: "#22c55e",
              }} />;
            })}
          </div>
          <span style={{ color: "#f59e0b", fontSize: "1rem", fontWeight: 600 }}>
            {streak + " streak!"}
          </span>
        </div>
      )}

      {/* Tap to continue hint */}
      <div style={{
        position: "absolute",
        bottom: "40px",
        color: "rgba(255,255,255,0.4)",
        fontSize: "0.9rem",
      }}>
        Tap anywhere to continue
      </div>
    </div>
  );
}
