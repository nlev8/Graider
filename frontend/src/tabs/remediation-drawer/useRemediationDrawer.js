import { useState, useEffect, useRef } from "react";
import * as api from "../../services/api";
import { validateQuestionList } from "./validation";
import { buildPublishPromise } from "./publishing";

// Generation payload, hoisted to module level in the CQ wave-6 split. The
// body was byte-identical in handleGenerate and regenerateAll pre-split
// (including the Phase 4.2 #12 dok comment) — built once here, called twice.
function buildRemediatePayload(standardCode, targetMode, targetStudentId, configCount, configDifficulty, configDok) {
  var payload = {
    standard_code: standardCode,
    target_mode: targetMode,
    count: configCount,
    difficulty: configDifficulty,
    dok: configDok,  // null = Auto; backend treats null as missing (Phase 4.2 #12).
  };
  if (targetMode === "single_student") payload.target_student_id = targetStudentId;
  return payload;
}

/**
 * State machine + handlers for RemediationDrawer, moved verbatim from the
 * component body in the CQ wave-6 split (tabs/remediation-drawer/*). Called
 * only by RemediationDrawer, so state lifetime is identical to pre-split:
 * one parent (ProgressRankGrid) conditionally unmounts the drawer, the other
 * (RemediationEffectiveness) keeps it mounted and toggles `open` — the
 * open/reset effect (dep array byte-identical) handles both.
 *
 * State machine: idle → generating → preview → (regenerating | publishing) → success | error
 */
export default function useRemediationDrawer({
  open, onClose, classId, standardCode, targetMode, targetStudentId, onPublished,
}) {
  var [state, setState] = useState("idle");
  var [error, setError] = useState(null);
  var [data, setData] = useState(null);  // {mode, questions|variants, target_student_ids?, ...}
  var [questions, setQuestions] = useState([]);
  // Phase 4.2 #2: personalized-mode state. `variants` is the per-student
  // array from the backend; activeVariantIndex is which one's preview is
  // currently visible. variants[i].questions is the EDITABLE questions for
  // that variant — we mirror state per variant so QuestionCard edits don't
  // collide across tabs.
  var [variants, setVariants] = useState([]);
  var [activeVariantIndex, setActiveVariantIndex] = useState(0);
  var [confirmRegenOpen, setConfirmRegenOpen] = useState(false);
  // Phase 4.2 #3: pre-generation config state. Default 8 + same matches
  // current behavior; teacher tweaks before clicking Generate.
  var [configCount, setConfigCount] = useState(8);
  var [configDifficulty, setConfigDifficulty] = useState("same");
  // Phase 4.2 #12: DOK control. Default null = "Auto" (no DOK directive
  // in prompt; preserves current behavior for backwards-compat).
  var [configDok, setConfigDok] = useState(null);
  // Validation error is shown inline in the preview state (not the error state).
  // Separate state slot so the drawer doesn't drop into the full-screen "error"
  // path (which is reserved for network/server errors).
  var [validationError, setValidationError] = useState(null);
  var cancelRef = useRef({ cancelled: false });
  var successTimerRef = useRef(null);

  // Reset on open / close.
  // Uses per-call localRef sentinels (matching AssessmentComparison.jsx precedent)
  // so a stale in-flight .then() can't sneak through after deps change or the
  // drawer closes — captured `localRef` is always the one its own fetch owns.
  useEffect(function() {
    if (!open) {
      if (cancelRef.current) cancelRef.current.cancelled = true;
      if (successTimerRef.current) { clearTimeout(successTimerRef.current); successTimerRef.current = null; }
      // Phase 4.2 #2 (Codex full-PR MINOR): clear preview state on close so
      // a stale variant array can't bleed into the next open. One parent
      // (ProgressRankGrid) conditionally unmounts the drawer, but
      // RemediationEffectiveness keeps it mounted and just toggles `open`.
      setData(null);
      setQuestions([]);
      setVariants([]);
      setActiveVariantIndex(0);
      setValidationError(null);
      setError(null);
      setState("idle");
      return;
    }
    // Phase 4.2 #3: drawer opens to "config" state, NOT auto-generating.
    // Teacher picks count + difficulty + clicks Generate (handleGenerate).
    setState("config");
    setError(null);
    setData(null);
    setQuestions([]);
    setVariants([]);
    setActiveVariantIndex(0);
    setValidationError(null);
    setConfigCount(8);  // Reset config to defaults on every open (not sticky).
    setConfigDifficulty("same");
    setConfigDok(null);  // Phase 4.2 #12: reset DOK to Auto on every open.
    return function() {
      if (cancelRef.current) cancelRef.current.cancelled = true;
      if (successTimerRef.current) {
        clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, [open, classId, standardCode, targetMode, targetStudentId]);

  // Phase 4.2 #3: extracted from the open-effect. Called when teacher
  // clicks Generate in the config state.
  function handleGenerate() {
    if (cancelRef.current) cancelRef.current.cancelled = true;
    var localRef = { cancelled: false };
    cancelRef.current = localRef;
    setState("generating");
    setError(null);
    setValidationError(null);
    var payload = buildRemediatePayload(standardCode, targetMode, targetStudentId, configCount, configDifficulty, configDok);
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (localRef.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Generation failed");
          setState("error");
          return;
        }
        setData(res);
        if (res.mode === "personalized" && Array.isArray(res.variants) && res.variants.length > 0) {
          setVariants(res.variants);
          setActiveVariantIndex(0);
          setQuestions([]);
        } else {
          setVariants([]);
          setQuestions(res.questions || []);
        }
        setState("preview");
      })
      .catch(function(e) {
        if (localRef.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  // Esc to close. If the regenerate-confirm dialog is open, Esc dismisses
  // just the dialog instead of the whole drawer.
  useEffect(function() {
    if (!open) return;
    function handler(e) {
      if (e.key === "Escape") {
        if (confirmRegenOpen) {
          setConfirmRegenOpen(false);
        } else {
          onClose();
        }
      }
    }
    document.addEventListener("keydown", handler);
    return function() { document.removeEventListener("keydown", handler); };
  }, [open, onClose, confirmRegenOpen]);

  function regenerateAll() {
    setConfirmRegenOpen(false);
    setValidationError(null);  // clear any stale validation message before regen
    // Cancel prior in-flight fetch so its late response can't overwrite this one.
    if (cancelRef.current) cancelRef.current.cancelled = true;
    var localRef = { cancelled: false };
    cancelRef.current = localRef;
    setState("regenerating");
    // Phase 4.2 #3: regenerate keeps current config (no config re-prompt).
    var payload = buildRemediatePayload(standardCode, targetMode, targetStudentId, configCount, configDifficulty, configDok);
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (localRef.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Regeneration failed");
          setState("error");
          return;
        }
        setData(res);
        // Phase 4.2 #2: same branching as initial fetch.
        if (res.mode === "personalized" && Array.isArray(res.variants) && res.variants.length > 0) {
          setVariants(res.variants);
          setActiveVariantIndex(0);
          setQuestions([]);
        } else {
          setVariants([]);
          setQuestions(res.questions || []);
        }
        setState("preview");
      })
      .catch(function(e) {
        if (localRef.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  // Phase 4.2 #2: derived state for personalized vs shared mode.
  var isPersonalized = data && data.mode === "personalized" && variants.length > 0;
  var activeVariant = isPersonalized ? variants[activeVariantIndex] : null;
  var activeQuestions = isPersonalized
    ? (activeVariant ? activeVariant.questions || [] : [])
    : questions;

  // Mutate the active set of questions (per-variant in personalized mode,
  // shared in shared mode).
  function setActiveQuestions(updater) {
    if (isPersonalized) {
      var next = variants.slice();
      var current = next[activeVariantIndex];
      if (current) {
        var newQs = typeof updater === "function" ? updater(current.questions || []) : updater;
        next[activeVariantIndex] = Object.assign({}, current, { questions: newQs });
        setVariants(next);
      }
    } else {
      var newQs2 = typeof updater === "function" ? updater(questions) : updater;
      setQuestions(newQs2);
    }
  }

  function validateBeforePublish() {
    // Phase 4.2 #2: in personalized mode, validate EACH variant. The first
    // failure switches the active tab to that variant and returns the error.
    if (isPersonalized) {
      for (var vi = 0; vi < variants.length; vi++) {
        var ve = validateQuestionList(variants[vi].questions || [], variants[vi].student_name);
        if (ve) {
          setActiveVariantIndex(vi);
          return ve;
        }
      }
      return null;
    }
    return validateQuestionList(questions, null);
  }

  function publish() {
    // Phase 4.2 #2: targeting-data check has two flavors. Shared mode uses
    // data.target_student_ids; personalized mode uses variants[].student_id.
    if (isPersonalized) {
      if (variants.length === 0) {
        setValidationError("No variants generated — please regenerate");
        return;
      }
    } else if (!data || !data.target_student_ids || !data.target_student_ids.length) {
      setValidationError("Targeting data missing — please regenerate");
      return;
    }
    var ve = validateBeforePublish();
    if (ve) { setValidationError(ve); return; }
    setValidationError(null);
    if (cancelRef.current) cancelRef.current.cancelled = true;
    var localRef = { cancelled: false };
    cancelRef.current = localRef;
    setState("publishing");

    // Promise construction moved verbatim to publishing.js (CQ wave-6 split).
    var publishPromise = buildPublishPromise({
      isPersonalized: isPersonalized, variants: variants, questions: questions,
      data: data, classId: classId, standardCode: standardCode,
    });

    publishPromise
      .then(function(res) {
        if (localRef.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Publish failed");
          setState("error");
          return;
        }
        setState("success");
        if (onPublished) onPublished();
        successTimerRef.current = setTimeout(function() {
          if (!localRef.cancelled) onClose();
        }, 2000);
      })
      .catch(function(e) {
        if (localRef.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  return {
    state, setState, error, data, questions, variants,
    activeVariantIndex, setActiveVariantIndex,
    confirmRegenOpen, setConfirmRegenOpen,
    configCount, setConfigCount, configDifficulty, setConfigDifficulty,
    configDok, setConfigDok, validationError,
    isPersonalized, activeVariant, activeQuestions, setActiveQuestions,
    handleGenerate, regenerateAll, publish,
  };
}
