// Pure helpers for QuestionPlayer — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). No behavior changes.

// Flatten sections into ordered question array
export function flattenSections(sections) {
  var result = [];
  (sections || []).forEach(function(section, sIdx) {
    (section.questions || []).forEach(function(q, qIdx) {
      result.push({
        question: q,
        sectionName: section.name,
        sectionInstructions: section.instructions,
        answerKey: sIdx + "-" + qIdx,
        sectionIndex: sIdx,
        questionIndex: qIdx,
      });
    });
  });
  return result;
}

// ── Correctness check for instant feedback (MC/TF only) ──
export function checkCorrectness(questionData, studentAns) {
  var qType = questionData.type || questionData.question_type || "multiple_choice";
  var correctAnswer = questionData.answer;
  if (!correctAnswer) return null;

  if (qType === "multiple_choice" && questionData.options) {
    // Student answer is an option index (0-3), correct answer is a letter like "B"
    var studentLetter = typeof studentAns === "number" ? String.fromCharCode(65 + studentAns) : "";
    var correctLetter = String(correctAnswer).toUpperCase().trim();
    if (correctLetter.length > 1 && correctLetter[1] === ")") correctLetter = correctLetter[0];
    return studentLetter === correctLetter;
  }
  if (qType === "true_false") {
    return String(studentAns).toLowerCase() === String(correctAnswer).toLowerCase();
  }
  return null; // Can't determine for other types
}

export function formatTime(seconds) {
  var m = Math.floor(seconds / 60);
  var s = seconds % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}

// ── Count answered ──
export function countAnswered(flatQuestions, answers) {
  var answeredCount = 0;
  flatQuestions.forEach(function(fq) {
    var fqType = fq.question.type || "";
    if (fqType === "matching" || (fq.question.terms && fq.question.terms.length > 0)) {
      var tc = (fq.question.terms || []).length;
      var mc2 = 0;
      for (var i = 0; i < tc; i++) {
        if (answers[fq.sectionIndex + "-" + fq.questionIndex + "-match-" + i] !== undefined) mc2++;
      }
      if (mc2 >= tc) answeredCount++;
    } else {
      var val = answers[fq.answerKey];
      if (val !== undefined && val !== "") answeredCount++;
    }
  });
  return answeredCount;
}
