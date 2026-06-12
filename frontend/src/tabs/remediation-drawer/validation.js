// Pre-publish validation for RemediationDrawer. Moved verbatim from
// RemediationDrawer.jsx in the CQ wave-6 split (tabs/remediation-drawer/*).
// Pure function — no component state; safe at module level.

// Pre-publish validation. Returns null on success, error string on failure.
// Verifies: ≥1 question, every question has non-empty text, MC has ≥2
// non-empty choices AND correct_answer references one of those choices.
// The remediation prompt allows the AI to mark the correct answer as
// a letter ("A"/"B"/"C"/"D"), the choice text, OR a numeric index — the
// validator accepts all three forms.
export function validateQuestionList(questionList, prefix) {
  if (!questionList || questionList.length < 1) {
    return (prefix ? prefix + ": " : "") + "At least one question required";
  }
  for (var i = 0; i < questionList.length; i++) {
    var q = questionList[i];
    if (!q.text || !q.text.trim()) {
      return (prefix ? prefix + ": " : "") + "Question " + (i + 1) + " has no text";
    }
    var t = (q.type || q.question_type || "").toLowerCase();
    if (t === "mcq" || t === "multiple_choice" || t === "mc") {
      var choices = q.choices || q.options || [];
      var nonEmptyChoices = [];
      for (var ci = 0; ci < choices.length; ci++) {
        var label = typeof choices[ci] === "string" ? choices[ci] : (choices[ci] && choices[ci].text);
        if (label && String(label).trim()) {
          nonEmptyChoices.push({ index: ci, label: String(label).trim() });
        }
      }
      if (nonEmptyChoices.length < 2) {
        return (prefix ? prefix + ": " : "") + "Question " + (i + 1) + " needs at least 2 choices";
      }
      var correct = q.correct_answer != null ? q.correct_answer : q.answer;
      if (correct == null || correct === "") {
        return (prefix ? prefix + ": " : "") + "Question " + (i + 1) + " has no correct answer";
      }
      var matched = false;
      if (typeof correct === "number") {
        matched = nonEmptyChoices.some(function(c) { return c.index === correct; });
      }
      if (!matched) {
        var s = String(correct).trim();
        if (/^[0-9]+$/.test(s)) {
          var idx = parseInt(s, 10);
          matched = nonEmptyChoices.some(function(c) { return c.index === idx; });
        }
        if (!matched && /^[A-Za-z]$/.test(s)) {
          var letterIdx = s.toUpperCase().charCodeAt(0) - 65;
          matched = nonEmptyChoices.some(function(c) { return c.index === letterIdx; });
        }
        if (!matched) {
          matched = nonEmptyChoices.some(function(c) { return c.label === s; });
        }
      }
      if (!matched) {
        return (prefix ? prefix + ": " : "") + "Question " + (i + 1) + " correct answer doesn't match any choice";
      }
    }
  }
  return null;
}
