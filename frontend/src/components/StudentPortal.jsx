/**
 * Student Portal Component
 * Allows students to join assessments via code and take them.
 *
 * CQ wave-6 split: the stage screens, style constants, theme toggle, and
 * handler factory live in ./student-portal/. This always-mounted shell owns
 * ALL state — the stage machine (join → name → assessment → results, plus
 * material), drafts, accommodations — and the effects, threading everything
 * to the screens via a single props spread. Each screen guards on `stage`
 * and returns null when inactive, preserving the original early-return
 * chain (the shell's final `return null` for an unknown stage is now five
 * nulls in a fragment — same empty DOM).
 */
import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import createPortalHandlers from "./student-portal/createPortalHandlers";
import { DELIVERY_PRESET_IDS } from "./student-portal/constants";
import JoinScreen from "./student-portal/JoinScreen";
import NameEntryScreen from "./student-portal/NameEntryScreen";
import AssessmentScreen from "./student-portal/AssessmentScreen";
import ResultsScreen from "./student-portal/ResultsScreen";
import MaterialScreen from "./student-portal/MaterialScreen";

export default function StudentPortal({
  preloadedAssessment = null,
  preloadedStudentName = "",
  contentId = null,
  studentToken = null,
  onBack = null,
  preloadedSettings = null,
} = {}) {
  // URL path parsing (join-code path only)
  const pathParts = window.location.pathname.split("/");
  const urlCode = pathParts[2] || ""; // /join/ABC123 -> ABC123

  // Determine initial state based on whether content was preloaded (Clever/class path)
  const isPreloaded = !!preloadedAssessment;
  const [stage, setStage] = useState(
    isPreloaded ? "assessment" : (urlCode ? "loading" : "join")
  );
  const [joinCode, setJoinCode] = useState(urlCode.toUpperCase());
  const [studentName, setStudentName] = useState(preloadedStudentName || "");
  const [assessment, setAssessment] = useState(preloadedAssessment ? {
    ...preloadedAssessment,
    settings: preloadedSettings || preloadedAssessment.settings || {},
    student_accommodations: (preloadedSettings || {}).student_accommodations || {},
  } : null);
  const [answers, setAnswers] = useState({});
  var [questionTimes, setQuestionTimes] = useState({});
  var [activeQuestionKey, setActiveQuestionKey] = useState(null);
  var [activeQuestionStartedAt, setActiveQuestionStartedAt] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [results, setResults] = useState(null);
  const [studentAccommodation, setStudentAccommodation] = useState(null);
  const [deliveryAccommodations, setDeliveryAccommodations] = useState([]);
  const [lightMode, setLightMode] = useState(function() {
    var saved = localStorage.getItem("portal-theme");
    if (saved) {
      document.body.setAttribute("data-theme", saved);
      return saved === "light";
    }
    return false;
  });
  var [markedForReview, setMarkedForReview] = useState([]);
  var [lastSavedAt, setLastSavedAt] = useState(null);
  var [draftLoaded, setDraftLoaded] = useState(false);
  var [resumedFromDraft, setResumedFromDraft] = useState(false);
  var [savingDraft, setSavingDraft] = useState(false);

  // Handler bodies moved verbatim to createPortalHandlers (CQ wave-6 split).
  // Recreated each render with the current state values + setters, exactly
  // like the inline consts they replaced. Not a hook, so hook order above
  // is untouched.
  var handlers = createPortalHandlers({
    joinCode: joinCode,
    studentName: studentName,
    assessment: assessment,
    isPreloaded: isPreloaded,
    contentId: contentId,
    studentToken: studentToken,
    answers: answers,
    questionTimes: questionTimes,
    activeQuestionKey: activeQuestionKey,
    activeQuestionStartedAt: activeQuestionStartedAt,
    startTime: startTime,
    markedForReview: markedForReview,
    setStage: setStage,
    setError: setError,
    setLoading: setLoading,
    setAssessment: setAssessment,
    setAnswers: setAnswers,
    setQuestionTimes: setQuestionTimes,
    setActiveQuestionKey: setActiveQuestionKey,
    setActiveQuestionStartedAt: setActiveQuestionStartedAt,
    setStartTime: setStartTime,
    setResults: setResults,
    setStudentAccommodation: setStudentAccommodation,
    setDeliveryAccommodations: setDeliveryAccommodations,
    setSavingDraft: setSavingDraft,
    setLastSavedAt: setLastSavedAt,
  });

  // Load assessment if URL has code (join-code path)
  useEffect(() => {
    if (urlCode && stage === "loading") {
      handlers.loadAssessment(urlCode);
    }
  }, [urlCode]);

  // Start timer and detect accommodations for preloaded (Clever/class) path
  useEffect(() => {
    if (isPreloaded && !startTime) {
      setStartTime(Date.now());
    }
    // Auto-detect accommodations for Clever students (they skip handleStartAssessment)
    if (isPreloaded && preloadedStudentName && assessment && assessment.student_accommodations) {
      var normalizedName = preloadedStudentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedName) {
          matchedAccom = entry[1];
        }
      });
      if (matchedAccom) {
        setStudentAccommodation(matchedAccom);
        var deliveryPresets = (matchedAccom.presets || []).filter(function(p) {
          return DELIVERY_PRESET_IDS.indexOf(p) !== -1;
        });
        setDeliveryAccommodations(deliveryPresets);
      }
    }
  }, [isPreloaded]);

  useEffect(function() {
    if (!contentId || !studentToken || draftLoaded) return;
    api.getDraft(contentId, studentToken).then(function(data) {
      if (data && data.draft) {
        setAnswers(data.draft.answers || {});
        setMarkedForReview(data.draft.marked_for_review || []);
        if (data.draft.question_times) {
          setQuestionTimes(data.draft.question_times);
        }
        setResumedFromDraft(true);
      }
      setDraftLoaded(true);
    }).catch(function() { setDraftLoaded(true); });
  }, [contentId, studentToken]);

  useEffect(function() {
    if (!contentId || !studentToken || !draftLoaded) return;
    if (Object.keys(answers).length === 0 && markedForReview.length === 0) return;
    var timer = setTimeout(function() {
      setSavingDraft(true);
      api.saveDraft(contentId, answers, markedForReview, questionTimes, studentToken).then(function(data) {
        if (data && data.success) {
          setLastSavedAt(Date.now());
        }
      }).catch(function() { /* silent retry on next change */ })
        .finally(function() { setSavingDraft(false); });
    }, 15000);
    return function() { clearTimeout(timer); };
  }, [answers, markedForReview, contentId, studentToken, draftLoaded]);

  // Everything the stage screens consume, in one spread (house pattern from
  // CQ waves 1-5). Stage state stays here; screens guard-and-return-null.
  var screenProps = {
    stage: stage,
    setStage: setStage,
    lightMode: lightMode,
    setLightMode: setLightMode,
    joinCode: joinCode,
    setJoinCode: setJoinCode,
    studentName: studentName,
    setStudentName: setStudentName,
    assessment: assessment,
    setAssessment: setAssessment,
    answers: answers,
    error: error,
    loading: loading,
    results: results,
    studentAccommodation: studentAccommodation,
    deliveryAccommodations: deliveryAccommodations,
    resumedFromDraft: resumedFromDraft,
    savingDraft: savingDraft,
    contentId: contentId,
    onBack: onBack,
    handleJoin: handlers.handleJoin,
    handleStartAssessment: handlers.handleStartAssessment,
    handleSubmit: handlers.handleSubmit,
    setAnswer: handlers.setAnswer,
    saveDraftNow: handlers.saveDraftNow,
  };

  return (
    <>
      <JoinScreen {...screenProps} />
      <NameEntryScreen {...screenProps} />
      <AssessmentScreen {...screenProps} />
      <ResultsScreen {...screenProps} />
      <MaterialScreen {...screenProps} />
    </>
  );
}
