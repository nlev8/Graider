import React, { useState, useMemo, useRef, useEffect } from "react";
import QuestionFeedback from "./QuestionFeedback";
import LessonBlock from "./LessonBlock";
import PlayerHeader from "./question-player/PlayerHeader";
import AccommodationBanner from "./question-player/AccommodationBanner";
import QuestionPrompt from "./question-player/QuestionPrompt";
import AnswerArea from "./question-player/AnswerArea";
import NavigationButtons from "./question-player/NavigationButtons";
import ConfirmSubmitModal from "./question-player/ConfirmSubmitModal";
import { getPlayerTheme } from "./question-player/theme";
import { flattenSections, checkCorrectness, countAnswered } from "./question-player/utils";

/**
 * QuestionPlayer — One-at-a-time question engine.
 *
 * Thin orchestrator (CQ wave 6 split): per-question navigation state
 * (current index, answers, timer) lives here; the question-type sub-renders
 * live in ./question-player/*.
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
  lightMode,
  lesson,
}) {
  // Flatten sections into ordered question array
  var flatQuestions = useMemo(function() {
    return flattenSections(sections);
  }, [sections]);

  var totalQuestions = flatQuestions.length;
  var [currentIndex, setCurrentIndex] = useState(0);
  var [showFeedback, setShowFeedback] = useState(false);
  var [feedbackResult, setFeedbackResult] = useState(null); // { isCorrect, points, maxPoints }
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
        setFeedbackResult({ isCorrect: correct, points: correct ? (q.points || 1) : 0, maxPoints: q.points || 1 });
        // Small delay so the UI shows the selection before overlay
        setTimeout(function() { setShowFeedback(true); }, 300);
      }
    }
  }

  function goToNext() {
    setShowFeedback(false);
    setFeedbackResult(null);
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
  }, []);

  // ── Count answered ──
  var answeredCount = countAnswered(flatQuestions, answers);

  // ── Styles ──
  // Light/dark theme colors
  var lm = lightMode || false;
  var theme = getPlayerTheme(lm);

  var questionContainerStyle = {
    maxWidth: "700px",
    margin: "0 auto",
    padding: "30px 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    minHeight: "calc(100vh - 120px)",
  };

  // ── Render ──
  var qType = q.type || q.question_type || "multiple_choice";

  return (
    <div>
      {/* ── Header ── */}
      <PlayerHeader
        lm={lm}
        theme={theme}
        title={title}
        studentName={studentName}
        settings={settings}
        isLargeText={isLargeText}
        isReducedDistractions={isReducedDistractions}
        timeRemaining={timeRemaining}
        currentIndex={currentIndex}
        totalQuestions={totalQuestions}
        isAnswered={isAnswered}
      />

      {/* ── Accommodation Banner ── */}
      <AccommodationBanner
        studentAccommodation={studentAccommodation}
        isReducedDistractions={isReducedDistractions}
        currentIndex={currentIndex}
        theme={theme}
      />

      {/* ── Question Area ── */}
      <div style={questionContainerStyle}>
        {/* Phase 4.2 #1: lesson at the top of question 1 only.
            Optional read; students who already know can scroll past. */}
        {currentIndex === 0 && lesson && <LessonBlock lesson={lesson} />}

        <QuestionPrompt
          showSectionHeader={showSectionHeader}
          current={current}
          q={q}
          isLargeText={isLargeText}
          isReadAloud={isReadAloud}
          theme={theme}
        />

        <AnswerArea
          q={q}
          qType={qType}
          isMatchingQuestion={isMatchingQuestion}
          current={current}
          answerKey={answerKey}
          currentAnswer={currentAnswer}
          isLargeText={isLargeText}
          theme={theme}
          handleAnswer={handleAnswer}
          onAnswer={onAnswer}
        />

        <NavigationButtons
          canGoBack={canGoBack}
          currentIndex={currentIndex}
          totalQuestions={totalQuestions}
          isAnswered={isAnswered}
          loading={loading}
          theme={theme}
          goToPrev={goToPrev}
          goToNext={goToNext}
          handleFinish={handleFinish}
        />
      </div>

      {/* ── Feedback Overlay (assignments, MC/TF only) ── */}
      {showFeedback && feedbackResult && (
        <QuestionFeedback
          isCorrect={feedbackResult.isCorrect}
          points={feedbackResult.points}
          maxPoints={feedbackResult.maxPoints}
          streak={streak}
          onNext={goToNext}
          hideStreak={isReducedDistractions}
        />
      )}

      {/* ── Confirmation Modal ── */}
      <ConfirmSubmitModal
        show={showConfirmModal}
        timedOut={timedOut}
        answeredCount={answeredCount}
        totalQuestions={totalQuestions}
        lm={lm}
        theme={theme}
        onCancel={function() { setShowConfirmModal(false); }}
        onConfirm={handleConfirmSubmit}
      />
    </div>
  );
}
