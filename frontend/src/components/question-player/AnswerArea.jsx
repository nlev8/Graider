import React from "react";
import MatchingCards from "../MatchingCards";
import Icon from "../Icon";

// ── Kahoot button colors ──
var KAHOOT_COLORS = ["#e21b3c", "#1368ce", "#d89e00", "#26890c"];
var KAHOOT_SHAPES = ["Triangle", "Diamond", "Circle", "Square"];

// Per-question-type answer inputs (Kahoot MC grid, true/false, matching,
// short answer / extended response) — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). data-testids are pinned by the e2e
// student-flow specs; do not change them.
export default function AnswerArea({
  q,
  qType,
  isMatchingQuestion,
  current,
  answerKey,
  currentAnswer,
  isLargeText,
  theme,
  handleAnswer,
  onAnswer,
}) {
  var textInputBg = theme.textInputBg;
  var textInputBorder = theme.textInputBorder;
  var textInputColor = theme.textInputColor;

  return (
    <>
      {/* ── Multiple Choice: Kahoot 2x2 grid ── */}
      {qType === "multiple_choice" && q.options && q.options.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: q.options.length <= 3 ? "1fr" : "1fr 1fr",
          gap: "12px",
          width: "100%",
          maxWidth: "600px",
        }}>
          {q.options.map(function(opt, oIdx) {
            var isSelected = currentAnswer === oIdx;
            var color = KAHOOT_COLORS[oIdx] || KAHOOT_COLORS[0];
            var shape = KAHOOT_SHAPES[oIdx] || KAHOOT_SHAPES[0];
            return (
              <button
                key={oIdx}
                onClick={function() { handleAnswer(answerKey, oIdx); }}
                data-testid={"mc-option-" + oIdx}
                style={{
                  background: color,
                  color: "white",
                  border: isSelected ? "4px solid white" : "4px solid transparent",
                  borderRadius: "12px",
                  padding: isLargeText ? "20px 16px" : "18px 14px",
                  fontSize: isLargeText ? "1.15rem" : "1rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  textAlign: "left",
                  opacity: isSelected ? 1 : 0.85,
                  transform: isSelected ? "scale(1.02)" : "scale(1)",
                  transition: "all 0.15s ease",
                  boxShadow: isSelected ? "0 0 20px rgba(255,255,255,0.3)" : "none",
                }}
              >
                <Icon name={shape} size={20} style={{ flexShrink: 0 }} />
                <span>{opt}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── True/False ── */}
      {qType === "true_false" && (
        <div style={{ display: "flex", gap: "16px", width: "100%", maxWidth: "500px" }}>
          {["True", "False"].map(function(tf) {
            var isSelected = currentAnswer === tf;
            var tfColor = tf === "True" ? "#22c55e" : "#ef4444";
            return (
              <button
                key={tf}
                onClick={function() { handleAnswer(answerKey, tf); }}
                data-testid={"tf-option-" + tf.toLowerCase()}
                style={{
                  flex: 1,
                  background: tfColor,
                  color: "white",
                  border: isSelected ? "4px solid white" : "4px solid transparent",
                  borderRadius: "12px",
                  padding: isLargeText ? "24px" : "20px",
                  fontSize: isLargeText ? "1.4rem" : "1.2rem",
                  fontWeight: 700,
                  cursor: "pointer",
                  opacity: isSelected ? 1 : 0.85,
                  transform: isSelected ? "scale(1.02)" : "scale(1)",
                  transition: "all 0.15s ease",
                  boxShadow: isSelected ? "0 0 20px rgba(255,255,255,0.3)" : "none",
                }}
              >
                {tf}
              </button>
            );
          })}
        </div>
      )}

      {/* ── Matching ── */}
      {isMatchingQuestion && (
        <div style={{ width: "100%" }}>
          <MatchingCards
            terms={q.terms}
            definitions={q.definitions}
            correctAnswer={q.answer}
            onMatch={function(matches, shuffledDefs) {
              Object.entries(matches).forEach(function(entry) {
                var tIdx = entry[0];
                var sdIdx = entry[1];
                var originalIdx = shuffledDefs && shuffledDefs[sdIdx] ? shuffledDefs[sdIdx].originalIdx : sdIdx;
                var matchKey = current.sectionIndex + "-" + current.questionIndex + "-match-" + tIdx;
                onAnswer(matchKey, String.fromCharCode(65 + originalIdx));
              });
            }}
          />
        </div>
      )}

      {/* ── Short Answer / Extended Response ── */}
      {(qType === "short_answer" || qType === "extended_response" ||
        (!q.options && qType !== "true_false" && !isMatchingQuestion)) && (
        <textarea
          value={currentAnswer || ""}
          onChange={function(e) { onAnswer(answerKey, e.target.value); }}
          data-testid="text-answer"
          placeholder={qType === "extended_response"
            ? "Write your extended response here. Include evidence and analysis to support your answer..."
            : "Type your answer here..."}
          rows={qType === "extended_response" || (q.points && q.points >= 4) ? 6 : 3}
          style={{
            width: "100%",
            maxWidth: "600px",
            padding: "15px",
            borderRadius: "10px",
            border: "2px solid " + textInputBorder,
            background: textInputBg,
            color: textInputColor,
            fontSize: isLargeText ? "1.15rem" : "1rem",
            resize: "vertical",
            lineHeight: 1.6,
            fontFamily: "inherit",
            outline: "none",
          }}
        />
      )}
    </>
  );
}
