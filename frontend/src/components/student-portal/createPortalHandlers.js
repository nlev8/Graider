import * as api from "../../services/api";
import { DELIVERY_PRESET_IDS } from "./constants";

// Handler bodies moved verbatim from StudentPortal.jsx (CQ wave-6 split;
// same factory pattern as district-setup/createConfigFormHandlers.js from
// wave 5). The shell owns all state and calls this factory on every render
// with the current state values + setters, so each handler closes over
// exactly the same per-render values it did when defined inline (no
// memoization here, same as before the split — handlers were recreated each
// render then too).
export default function createPortalHandlers(ctx) {
  var joinCode = ctx.joinCode;
  var studentName = ctx.studentName;
  var assessment = ctx.assessment;
  var isPreloaded = ctx.isPreloaded;
  var contentId = ctx.contentId;
  var studentToken = ctx.studentToken;
  var answers = ctx.answers;
  var questionTimes = ctx.questionTimes;
  var activeQuestionKey = ctx.activeQuestionKey;
  var activeQuestionStartedAt = ctx.activeQuestionStartedAt;
  var startTime = ctx.startTime;
  var markedForReview = ctx.markedForReview;
  var setStage = ctx.setStage;
  var setError = ctx.setError;
  var setLoading = ctx.setLoading;
  var setAssessment = ctx.setAssessment;
  var setAnswers = ctx.setAnswers;
  var setQuestionTimes = ctx.setQuestionTimes;
  var setActiveQuestionKey = ctx.setActiveQuestionKey;
  var setActiveQuestionStartedAt = ctx.setActiveQuestionStartedAt;
  var setStartTime = ctx.setStartTime;
  var setResults = ctx.setResults;
  var setStudentAccommodation = ctx.setStudentAccommodation;
  var setDeliveryAccommodations = ctx.setDeliveryAccommodations;
  var setSavingDraft = ctx.setSavingDraft;
  var setLastSavedAt = ctx.setLastSavedAt;

  const loadAssessment = async (code) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getStudentAssessment(code);
      if (data.error) {
        setError(data.error);
        setStage("join");
      } else if (data.content_type && ["study_guide", "flashcards", "slide_deck", "mind_map", "audio_overview", "video_overview", "infographic", "data_table"].indexOf(data.content_type) !== -1) {
        setAssessment(data);
        setStage("material");
      } else {
        setAssessment(data);
        setStage("name");
      }
    } catch (e) {
      setError("Could not load assessment. Check your code and try again.");
      setStage("join");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) {
      setError("Please enter a join code");
      return;
    }
    await loadAssessment(joinCode.toUpperCase());
  };

  const handleStartAssessment = () => {
    if (!studentName.trim()) {
      setError("Please enter your name");
      return;
    }

    // Check if this is a restricted assessment (makeup exam)
    const settings = assessment?.settings || {};
    const isMakeup = settings.is_makeup || false;
    const restrictedStudents = settings.restricted_students || [];

    if (isMakeup && restrictedStudents.length > 0) {
      const normalizedName = studentName.trim().toLowerCase();
      const isAllowed = restrictedStudents.some(
        (s) => s.toLowerCase() === normalizedName
      );
      if (!isAllowed) {
        setError("This assessment is restricted to specific students. If you believe this is an error, please contact your teacher.");
        return;
      }
    }

    // Check if student has accommodations (case-insensitive name match)
    if (assessment?.student_accommodations) {
      var normalizedAccomName = studentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedAccomName) {
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

    setStartTime(Date.now());
    setStage("assessment");
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    const timeTaken = Math.round((Date.now() - startTime) / 1000);
    try {
      var data;
      if (isPreloaded && contentId && studentToken) {
        // Finalize current question time before submit
        var finalTimes = Object.assign({}, questionTimes);
        if (activeQuestionKey && activeQuestionStartedAt) {
          var finalElapsed = Math.round((Date.now() - activeQuestionStartedAt) / 1000);
          finalTimes[activeQuestionKey] = (finalTimes[activeQuestionKey] || 0) + finalElapsed;
        }
        // Class-based submission (Clever/authenticated student)
        // Phase 4.2: URL is /api/student/class-submit/ (was /api/student/submit/,
        // shadowed by join-code handler). See spec 2026-04-27-phase4.2-submit-routing-fix-design.md
        var response = await fetch("/api/student/class-submit/" + contentId, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Student-Token": studentToken,
          },
          body: JSON.stringify({ answers: answers, time_taken_seconds: timeTaken, question_times: finalTimes }),
        });
        data = await response.json();
      } else {
        // Join-code submission (anonymous)
        data = await api.submitStudentAssessment(
          joinCode,
          studentName,
          answers,
          timeTaken
        );
      }
      if (data.error) {
        setError(data.error);
        if (data.previous_results) {
          setResults(data.previous_results);
          setStage("results");
        }
      } else {
        if (data.grading_status === "pending_review") {
          setResults({
            grading_status: "pending_review",
            message: data.message,
            is_late: data.is_late,
          });
        } else if (data.grading_status === "partial") {
          setResults({
            grading_status: "partial",
            mc_correct: data.mc_correct,
            mc_total: data.mc_total,
            written_pending: data.written_pending,
            message: data.message,
            questions: data.detailed_results,
            is_late: data.is_late,
          });
        } else {
          setResults({
            score: data.score,
            total_points: data.total_points,
            percentage: data.percentage,
            feedback_summary: data.feedback_summary,
            questions: data.detailed_results,
            is_late: data.is_late,
          });
        }
        setStage("results");
      }
    } catch (e) {
      setError("Failed to submit. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const setAnswer = (key, value) => {
    var now = Date.now();
    if (activeQuestionKey && activeQuestionKey !== key && activeQuestionStartedAt) {
      var elapsed = Math.round((now - activeQuestionStartedAt) / 1000);
      setQuestionTimes(function(prev) {
        var next = Object.assign({}, prev);
        next[activeQuestionKey] = (next[activeQuestionKey] || 0) + elapsed;
        return next;
      });
    }
    if (activeQuestionKey !== key) {
      setActiveQuestionKey(key);
      setActiveQuestionStartedAt(now);
    } else if (!activeQuestionStartedAt) {
      setActiveQuestionStartedAt(now);
    }
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  var saveDraftNow = async function() {
    if (!contentId || !studentToken) return;
    setSavingDraft(true);
    try {
      var data = await api.saveDraft(contentId, answers, markedForReview, questionTimes, studentToken);
      if (data && data.success) {
        setLastSavedAt(Date.now());
        alert('Draft saved. You can close this tab and come back later.');
      }
    } catch (e) {
      alert('Failed to save draft: ' + e.message);
    } finally {
      setSavingDraft(false);
    }
  };

  return {
    loadAssessment: loadAssessment,
    handleJoin: handleJoin,
    handleStartAssessment: handleStartAssessment,
    handleSubmit: handleSubmit,
    setAnswer: setAnswer,
    saveDraftNow: saveDraftNow,
  };
}
