import React from "react";
import Icon from "../Icon";

// ── Read Aloud ──
function speakText(text) {
  var utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

// Section header + question text + read-aloud button — extracted verbatim
// from QuestionPlayer.jsx (CQ wave 6 split).
export default function QuestionPrompt({
  showSectionHeader,
  current,
  q,
  isLargeText,
  isReadAloud,
  theme,
}) {
  var subtextColor = theme.subtextColor;
  var sectionColor = theme.sectionColor;

  return (
    <>
      {/* Section header */}
      {showSectionHeader && (
        <div style={{ textAlign: "center", marginBottom: "20px", width: "100%" }}>
          <h2 style={{ fontSize: isLargeText ? "1.4rem" : "1.2rem", fontWeight: 700, color: sectionColor, margin: "0 0 5px" }}>
            {current.sectionName}
          </h2>
          {current.sectionInstructions && (
            <p style={{ color: subtextColor, fontStyle: "italic", margin: 0, fontSize: "0.95rem" }}>
              {current.sectionInstructions}
            </p>
          )}
        </div>
      )}

      {/* Question text */}
      <div style={{
        textAlign: "center",
        marginBottom: "30px",
        width: "100%",
        padding: "20px",
      }}>
        <div style={{ fontSize: "0.9rem", color: subtextColor, marginBottom: "8px" }}>
          {q.points + " point" + (q.points > 1 ? "s" : "")}
        </div>
        <h3 style={{
          fontSize: isLargeText ? "1.6rem" : "1.3rem",
          fontWeight: 700,
          lineHeight: 1.4,
          margin: 0,
        }}>
          {q.number + ". " + q.question}
        </h3>
        {isReadAloud && (
          <button
            onClick={function() { speakText(q.question); }}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: "rgba(99,102,241,0.8)", padding: "8px", marginTop: "8px",
              fontSize: "1.2rem",
            }}
            title="Read aloud"
          >
            <Icon name="Volume2" size={20} />
          </button>
        )}
      </div>
    </>
  );
}
