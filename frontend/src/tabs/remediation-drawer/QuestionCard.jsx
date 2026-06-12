import React from "react";

// Editable question card. Moved verbatim from RemediationDrawer.jsx (where it
// was a second top-level function, 38 LOC) in the CQ wave-6 split.
export default function QuestionCard({ index, question, disabled, onChange }) {
  var t = (question.type || question.question_type || "").toLowerCase();
  var isMC = t === "mcq" || t === "multiple_choice" || t === "mc";
  function setText(v) { onChange(Object.assign({}, question, { text: v })); }
  function setChoice(i, v) {
    var choices = (question.choices || question.options || []).slice();
    if (typeof choices[i] === "string") choices[i] = v;
    else choices[i] = Object.assign({}, choices[i], { text: v });
    onChange(Object.assign({}, question, { choices: choices }));
  }
  function setCorrect(v) { onChange(Object.assign({}, question, { correct_answer: v })); }
  return (
    <div style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
        <strong style={{ fontSize: "0.85rem" }}>Q{index + 1}</strong>
        <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>{isMC ? "MC" : "SA"}</span>
      </div>
      <textarea value={question.text || ""} disabled={disabled}
                onChange={function(e) { setText(e.target.value); }}
                style={{ width: "100%", minHeight: "60px", padding: "6px",
                         border: "1px solid var(--glass-border)", borderRadius: "4px", fontSize: "0.85rem" }} />
      {isMC && (question.choices || question.options || []).map(function(c, ci) {
        var label = typeof c === "string" ? c : (c.text || "");
        return (
          <div key={ci} style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
            <input type="radio" name={"correct-" + index} disabled={disabled}
                   checked={question.correct_answer === ci || question.correct_answer === label}
                   onChange={function() { setCorrect(ci); }} />
            <input type="text" value={label} disabled={disabled}
                   onChange={function(e) { setChoice(ci, e.target.value); }}
                   style={{ flex: 1, padding: "4px", border: "1px solid var(--glass-border)",
                            borderRadius: "4px", fontSize: "0.8rem" }} />
          </div>
        );
      })}
    </div>
  );
}
