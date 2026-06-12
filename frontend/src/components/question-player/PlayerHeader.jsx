import React from "react";
import { formatTime } from "./utils";

// Sticky header (title, student, due date, timer, counter, progress bar) —
// extracted verbatim from QuestionPlayer.jsx (CQ wave 6 split).
export default function PlayerHeader({
  lm,
  theme,
  title,
  studentName,
  settings,
  isLargeText,
  isReducedDistractions,
  timeRemaining,
  currentIndex,
  totalQuestions,
  isAnswered,
}) {
  var subtextColor = theme.subtextColor;
  var borderClr = theme.borderClr;
  var progressTrack = theme.progressTrack;

  var headerStyle = {
    position: "sticky",
    top: 0,
    background: lm ? "rgba(248,250,252,0.95)" : "rgba(15, 15, 35, 0.95)",
    borderBottom: "1px solid " + borderClr,
    padding: "12px 20px",
    zIndex: 100,
  };

  return (
    <div style={headerStyle}>
      <div style={{ maxWidth: "700px", margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div>
            <h1 style={{ fontSize: isLargeText ? "1.3rem" : "1.1rem", fontWeight: 700, margin: 0 }}>{title}</h1>
            <span style={{ fontSize: "0.85rem", color: subtextColor }}>{studentName}</span>
            {settings.due_date && (
              <span style={{ fontSize: "0.8rem", color: "rgba(245,158,11,0.8)", marginLeft: "12px" }}>
                {"Due: " + new Date(settings.due_date).toLocaleDateString()}
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            {/* Timer */}
            {timeRemaining !== null && !isReducedDistractions && (
              <span style={{
                fontSize: "1.1rem",
                fontWeight: 600,
                fontFamily: "monospace",
                color: timeRemaining <= 120 ? "#ef4444" : "rgba(255,255,255,0.8)",
              }}>
                {formatTime(timeRemaining)}
              </span>
            )}
            {/* Question counter */}
            {!isReducedDistractions && (
              <span style={{ fontSize: "0.9rem", color: subtextColor }}>
                {"Question " + (currentIndex + 1) + " of " + totalQuestions}
              </span>
            )}
          </div>
        </div>
        {/* Progress bar */}
        {!isReducedDistractions && (
          <div style={{ height: "4px", background: progressTrack, borderRadius: "2px" }}>
            <div style={{
              height: "100%",
              width: (((currentIndex + (isAnswered ? 1 : 0)) / totalQuestions) * 100) + "%",
              background: "#8b5cf6",
              borderRadius: "2px",
              transition: "width 0.3s ease",
            }} />
          </div>
        )}
      </div>
    </div>
  );
}
