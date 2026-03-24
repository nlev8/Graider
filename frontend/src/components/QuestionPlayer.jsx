import React, { useState, useMemo, useCallback, useRef, useEffect } from "react";
import MatchingCards from "./MatchingCards";
import QuestionFeedback from "./QuestionFeedback";

/**
 * QuestionPlayer — One-at-a-time question engine.
 *
 * Props:
 *   sections: array — assessment sections with questions[]
 *   contentType: "assessment" | "assignment"
 *   settings: object — publish settings
 *   accommodations: string[] — delivery accommodation preset IDs
 *   effectiveTimeLimit: number|null — minutes (with accommodation multipliers)
 *   studentName: string
 *   title: string
 *   answers: object — current answers dict
 *   onAnswer: (key, value) => void
 *   onSubmit: () => void
 *   loading: boolean — submission in progress
 *   assessment: object — full assessment (for accommodation banner)
 *   studentAccommodation: object|null — matched accommodation data
 */
export default function QuestionPlayer({
  sections,
  contentType,
  settings,
  accommodations,
  effectiveTimeLimit,
  studentName,
  title,
  answers,
  onAnswer,
  onSubmit,
  loading,
  assessment,
  studentAccommodation,
}) {
  // Flatten sections into ordered question array
  var flatQuestions = useMemo(function() {
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
  }, [sections]);

  var totalQuestions = flatQuestions.length;
  var [currentIndex, setCurrentIndex] = useState(0);
  var [showFeedback, setShowFeedback] = useState(false);
  var [streak, setStreak] = useState(0);
  var [showConfirmModal, setShowConfirmModal] = useState(false);
  var [timeRemaining, setTimeRemaining] = useState(
    effectiveTimeLimit ? effectiveTimeLimit * 60 : null
  );
  var [timedOut, setTimedOut] = useState(false);
  var timerRef = useRef(null);

  // Accommodation flags
  var isLargeText = (accommodations || []).indexOf("large_text") !== -1;
  var isReadAloud = (accommodations || []).indexOf("read_aloud") !== -1;
  var isReducedDistractions = (accommodations || []).indexOf("reduced_distractions") !== -1;

  var isAssignment = contentType === "assignment";
  var canGoBack = isAssignment;

  var current = flatQuestions[currentIndex];
  if (!current) return null;

  var q = current.question;
  var answerKey = current.answerKey;
  var currentAnswer = answers[answerKey];

  // Check if current question is answered
  var isAnswered = currentAnswer !== undefined && currentAnswer !== "";

  // For matching, check if all pairs are matched
  var isMatchingQuestion = q.type === "matching" || (q.terms && q.terms.length > 0 && q.definitions && q.definitions.length > 0);
  if (isMatchingQuestion) {
    var matchCount = 0;
    var termCount = (q.terms || []).length;
    for (var mi = 0; mi < termCount; mi++) {
      if (answers[current.sectionIndex + "-" + current.questionIndex + "-match-" + mi] !== undefined) {
        matchCount++;
      }
    }
    isAnswered = matchCount >= termCount;
  }

  // Show section header when section changes
  var showSectionHeader = currentIndex === 0 ||
    flatQuestions[currentIndex - 1].sectionName !== current.sectionName;

  // ── Correctness check for instant feedback (MC/TF only) ──
  function checkCorrectness(questionData, studentAns) {
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

  // ── Navigation ──
  function handleAnswer(key, value) {
    onAnswer(key, value);

    // For assignments with MC/TF, show feedback after answering
    var qType = q.type || q.question_type || "multiple_choice";
    if (isAssignment && (qType === "multiple_choice" || qType === "true_false")) {
      var correct = checkCorrectness(q, value);
      if (correct !== null) {
        if (correct) {
          setStreak(function(s) { return s + 1; });
        } else {
          setStreak(0);
        }
        // Small delay so the UI shows the selection before overlay
        setTimeout(function() { setShowFeedback(true); }, 300);
      }
    }
  }

  function goToNext() {
    setShowFeedback(false);
    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  }

  function goToPrev() {
    if (canGoBack && currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  }

  function handleFinish() {
    setShowConfirmModal(true);
  }

  function handleConfirmSubmit() {
    setShowConfirmModal(false);
    onSubmit();
  }

  // ── Timer ──
  useEffect(function() {
    if (timeRemaining === null) return;
    timerRef.current = setInterval(function() {
      setTimeRemaining(function(prev) {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          setTimedOut(true);
          setShowConfirmModal(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return function() { clearInterval(timerRef.current); };
  }, [timeRemaining !== null]);

  function formatTime(seconds) {
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  // ── Count answered ──
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

  // ── Kahoot button colors ──
  var KAHOOT_COLORS = ["#e21b3c", "#1368ce", "#d89e00", "#26890c"];
  var KAHOOT_SHAPES = [
    String.fromCharCode(9650),  // triangle
    String.fromCharCode(9670),  // diamond
    String.fromCharCode(9679),  // circle
    String.fromCharCode(9632),  // square
  ];

  // ── Styles ──
  var headerStyle = {
    position: "sticky",
    top: 0,
    background: "rgba(15, 15, 35, 0.95)",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
    padding: "12px 20px",
    zIndex: 100,
  };

  var questionContainerStyle = {
    maxWidth: "700px",
    margin: "0 auto",
    padding: "30px 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    minHeight: "calc(100vh - 120px)",
  };

  // ── Read Aloud ──
  function speakText(text) {
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  // ── Render ──
  var qType = q.type || q.question_type || "multiple_choice";

  return (
    <div>
      {/* ── Header ── */}
      <div style={headerStyle}>
        <div style={{ maxWidth: "700px", margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <div>
              <h1 style={{ fontSize: isLargeText ? "1.3rem" : "1.1rem", fontWeight: 700, margin: 0 }}>{title}</h1>
              <span style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>{studentName}</span>
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
                <span style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.7)" }}>
                  {"Question " + (currentIndex + 1) + " of " + totalQuestions}
                </span>
              )}
            </div>
          </div>
          {/* Progress bar */}
          {!isReducedDistractions && (
            <div style={{ height: "4px", background: "rgba(255,255,255,0.1)", borderRadius: "2px" }}>
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

      {/* ── Accommodation Banner ── */}
      {studentAccommodation && !isReducedDistractions && currentIndex === 0 && (
        <div style={{ maxWidth: "700px", margin: "20px auto 0", padding: "0 20px" }}>
          <div style={{
            background: "rgba(59, 130, 246, 0.15)",
            border: "1px solid rgba(59, 130, 246, 0.4)",
            borderRadius: "10px",
            padding: "15px 20px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
              <span style={{ fontSize: "1.2rem" }}>
                {String.fromCharCode(128203)}
              </span>
              <strong style={{ color: "#60a5fa" }}>Your Accommodations</strong>
            </div>
            {studentAccommodation.presets && studentAccommodation.presets.length > 0 && (
              <ul style={{ margin: "0 0 10px 20px", padding: 0, color: "rgba(255,255,255,0.8)", fontSize: "0.95rem" }}>
                {studentAccommodation.presets.map(function(preset, idx) {
                  var names = {
                    simplified_language: "Simplified Language",
                    effort_focused: "Effort-Focused Feedback",
                    extra_encouragement: "Extra Encouragement",
                    chunked_feedback: "Chunked Feedback",
                    modified_expectations: "Modified Expectations",
                    visual_structure: "Visual Structure",
                    read_aloud_friendly: "Read-Aloud Friendly",
                    growth_mindset: "Growth Mindset",
                    ell_support: "ELL Support",
                    extended_time_1_5x: "Extended Time (1.5x)",
                    extended_time_2x: "Extended Time (2x)",
                    extended_time_unlimited: "Extended Time (Unlimited)",
                    large_text: "Large Text",
                    read_aloud: "Read Aloud",
                    reduced_distractions: "Reduced Distractions",
                  };
                  return <li key={idx} style={{ marginBottom: "5px" }}>{names[preset] || preset.replace(/_/g, " ")}</li>;
                })}
              </ul>
            )}
            {studentAccommodation.custom_notes && (
              <p style={{ margin: 0, color: "rgba(255,255,255,0.7)", fontSize: "0.9rem", fontStyle: "italic" }}>
                {studentAccommodation.custom_notes}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Question Area ── */}
      <div style={questionContainerStyle}>
        {/* Section header */}
        {showSectionHeader && (
          <div style={{ textAlign: "center", marginBottom: "20px", width: "100%" }}>
            <h2 style={{ fontSize: isLargeText ? "1.4rem" : "1.2rem", fontWeight: 700, color: "#8b5cf6", margin: "0 0 5px" }}>
              {current.sectionName}
            </h2>
            {current.sectionInstructions && (
              <p style={{ color: "rgba(255,255,255,0.6)", fontStyle: "italic", margin: 0, fontSize: "0.95rem" }}>
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
          <div style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.5)", marginBottom: "8px" }}>
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
              {String.fromCharCode(128264)}
            </button>
          )}
        </div>

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
                  <span style={{ fontSize: "1.3rem", flexShrink: 0 }}>{shape}</span>
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
              border: "2px solid rgba(255,255,255,0.2)",
              background: "rgba(0,0,0,0.3)",
              color: "white",
              fontSize: isLargeText ? "1.15rem" : "1rem",
              resize: "vertical",
              lineHeight: 1.6,
              fontFamily: "inherit",
              outline: "none",
            }}
          />
        )}

        {/* ── Navigation Buttons ── */}
        <div style={{
          display: "flex",
          gap: "12px",
          marginTop: "30px",
          width: "100%",
          maxWidth: "600px",
          justifyContent: "center",
        }}>
          {canGoBack && currentIndex > 0 && (
            <button
              onClick={goToPrev}
              data-testid="btn-back"
              style={{
                padding: "14px 28px",
                fontSize: "1.05rem",
                fontWeight: 600,
                border: "2px solid rgba(255,255,255,0.3)",
                borderRadius: "10px",
                cursor: "pointer",
                background: "transparent",
                color: "white",
              }}
            >
              {String.fromCharCode(8592) + " Back"}
            </button>
          )}
          {currentIndex < totalQuestions - 1 ? (
            <button
              onClick={goToNext}
              disabled={!isAnswered && !canGoBack}
              data-testid="btn-next"
              style={{
                flex: 1,
                padding: "14px 28px",
                fontSize: "1.05rem",
                fontWeight: 600,
                border: "none",
                borderRadius: "10px",
                cursor: isAnswered || canGoBack ? "pointer" : "not-allowed",
                background: isAnswered ? "linear-gradient(135deg, #8b5cf6, #6366f1)" : "rgba(255,255,255,0.1)",
                color: isAnswered ? "white" : "rgba(255,255,255,0.4)",
                transition: "all 0.2s ease",
              }}
            >
              {"Next " + String.fromCharCode(8594)}
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={loading}
              data-testid="btn-finish"
              style={{
                flex: 1,
                padding: "14px 28px",
                fontSize: "1.05rem",
                fontWeight: 600,
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                background: "linear-gradient(135deg, #22c55e, #16a34a)",
                color: "white",
              }}
            >
              {loading ? "Submitting..." : "Finish"}
            </button>
          )}
        </div>
      </div>

      {/* ── Feedback Overlay (assignments, MC/TF only) ── */}
      {showFeedback && (function() {
        var correct = checkCorrectness(q, currentAnswer);
        return (
          <QuestionFeedback
            isCorrect={correct}
            points={correct ? (q.points || 1) : 0}
            maxPoints={q.points || 1}
            streak={streak}
            onNext={goToNext}
          />
        );
      })()}

      {/* ── Confirmation Modal ── */}
      {showConfirmModal && (
        <div style={{
          position: "fixed",
          top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0, 0, 0, 0.85)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
        }}>
          <div style={{
            background: "rgba(30, 30, 60, 0.95)",
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: "16px",
            padding: "30px",
            maxWidth: "400px",
            width: "90%",
            textAlign: "center",
          }}>
            <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "15px" }}>
              {timedOut ? "Time's Up!" : "Submit?"}
            </h2>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "8px" }}>
              {"You answered " + answeredCount + " of " + totalQuestions + " questions."}
            </p>
            {answeredCount < totalQuestions && (
              <p style={{ color: "#f59e0b", fontSize: "0.9rem", marginBottom: "20px" }}>
                {(totalQuestions - answeredCount) + " question" + (totalQuestions - answeredCount !== 1 ? "s" : "") + " unanswered"}
              </p>
            )}
            <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
              {!timedOut && (
                <button
                  onClick={function() { setShowConfirmModal(false); }}
                  data-testid="btn-go-back"
                  style={{
                    padding: "12px 24px",
                    fontSize: "1rem",
                    fontWeight: 600,
                    border: "2px solid rgba(255,255,255,0.3)",
                    borderRadius: "10px",
                    cursor: "pointer",
                    background: "transparent",
                    color: "white",
                  }}
                >
                  Go Back
                </button>
              )}
              <button
                onClick={handleConfirmSubmit}
                data-testid="btn-confirm-submit"
                style={{
                  padding: "12px 24px",
                  fontSize: "1rem",
                  fontWeight: 600,
                  border: "none",
                  borderRadius: "10px",
                  cursor: "pointer",
                  background: "linear-gradient(135deg, #22c55e, #16a34a)",
                  color: "white",
                }}
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
