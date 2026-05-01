import React, { useState, useEffect, useRef } from "react";
import * as api from "../services/api";
import LessonBlock from "../components/LessonBlock";

/**
 * Phase 4 — Remediation Drawer.
 * Phase 4.2 #1: also previews + round-trips a lesson dict to publish payload.
 *
 * State machine: idle → generating → preview → (regenerating | publishing) → success | error
 */
export default function RemediationDrawer({
  open, onClose, classId, standardCode, targetMode, targetStudentId, targetStudentName,
  onPublished,
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
    var payload = {
      standard_code: standardCode,
      target_mode: targetMode,
      count: configCount,
      difficulty: configDifficulty,
      dok: configDok,  // null = Auto; backend treats null as missing (Phase 4.2 #12).
    };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
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
    var payload = {
      standard_code: standardCode,
      target_mode: targetMode,
      count: configCount,
      difficulty: configDifficulty,
      dok: configDok,  // null = Auto; backend treats null as missing (Phase 4.2 #12).
    };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
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

  // Pre-publish validation. Returns null on success, error string on failure.
  // Verifies: ≥1 question, every question has non-empty text, MC has ≥2
  // non-empty choices AND correct_answer references one of those choices.
  // The remediation prompt allows the AI to mark the correct answer as
  // a letter ("A"/"B"/"C"/"D"), the choice text, OR a numeric index — the
  // validator accepts all three forms.
  function validateQuestionList(questionList, prefix) {
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

    var publishPromise;
    if (isPersonalized) {
      // Phase 4.2 #2: atomic batch publish — N rows written in a single
      // PostgREST INSERT. The drawer issues ONE call, not N.
      var items = variants.map(function(v) {
        var contentPayload = { questions: v.questions || [] };
        if (v.lesson) contentPayload.lesson = v.lesson;
        return {
          content: contentPayload,
          target_student_ids: [v.student_id],
          settings: { target_standard: standardCode },
          title: "Remediation: " + standardCode,
        };
      });
      publishPromise = api.publishToClassBatch(classId, items, "assessment");
    } else {
      // Phase 4.2 #1: round-trip the validated lesson dict (or null) through
      // to publish_to_class so it lands in published_content.content JSONB.
      var sharedContentPayload = { questions: questions };
      if (data && data.lesson) sharedContentPayload.lesson = data.lesson;
      publishPromise = api.publishToClass(
        classId,
        sharedContentPayload,
        "assessment",
        "Remediation: " + standardCode,
        // Phase 4.2 #6: persist target_standard so the Effectiveness dashboard
        // can attribute mastery delta without parsing title.
        { target_standard: standardCode },
        null,  // dueDate — none
        data.target_student_ids,
      );
    }

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

  if (!open) return null;

  var disabled = state === "generating" || state === "regenerating" || state === "publishing";
  // Phase 4.2 #2: in personalized mode, nTargets comes from variants.length;
  // in shared mode, from data.target_student_ids.
  var nTargets = isPersonalized
    ? variants.length
    : (data && data.target_student_ids ? data.target_student_ids.length : 0);
  var subtitle = "";
  if (targetMode === "single_student") {
    subtitle = "for " + (targetStudentName || "student");
  } else if (isPersonalized) {
    subtitle = "for " + nTargets + " student" + (nTargets === 1 ? "" : "s") + " (personalized)";
  } else if (data && data.target_student_ids) {
    subtitle = "for " + nTargets + " red-tier student" + (nTargets === 1 ? "" : "s");
  }

  return (
    <>
      <div onClick={onClose}
           style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                    background: "rgba(0,0,0,0.4)", zIndex: 9499 }} />
      <div style={{
        position: "fixed", top: 0, right: 0, height: "100vh",
        width: "min(720px, 96vw)", background: "var(--card-bg)",
        zIndex: 9500, display: "flex", flexDirection: "column",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.3)",
      }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--glass-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Remediation: {standardCode}</h3>
              <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>{subtitle}</p>
            </div>
            <button onClick={onClose} disabled={disabled}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
              {String.fromCharCode(10005)}
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {state === "config" ? (
            /* Phase 4.2 #3: pre-generation config dialog. Slider for count
               (3-15) + three-button difficulty toggle. */
            <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "480px" }}>
              <div>
                <h4 style={{ margin: "0 0 4px", fontSize: "0.95rem", fontWeight: 700 }}>Configure remediation</h4>
                <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Set length and difficulty before generating.
                </p>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
                  Question count: <span style={{ color: "var(--accent-primary)" }}>{configCount}</span>
                </label>
                <input
                  type="range"
                  min={3}
                  max={15}
                  step={1}
                  value={configCount}
                  onChange={function(e) { setConfigCount(parseInt(e.target.value, 10)); }}
                  disabled={disabled}
                  style={{ width: "100%" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "2px" }}>
                  <span>3</span>
                  <span>15</span>
                </div>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
                  Difficulty
                </label>
                <div style={{ display: "flex", gap: "6px" }}>
                  {["easier", "same", "harder"].map(function(diff) {
                    var active = diff === configDifficulty;
                    return (
                      <button key={diff}
                              onClick={function() { setConfigDifficulty(diff); }}
                              disabled={disabled}
                              style={{
                                flex: 1, padding: "8px 12px", fontSize: "0.85rem",
                                borderRadius: "6px", fontWeight: active ? 700 : 500,
                                border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                background: active ? "rgba(99,102,241,0.15)" : "transparent",
                                color: active ? "var(--accent-primary)" : "var(--text-primary)",
                                cursor: disabled ? "not-allowed" : "pointer",
                                textTransform: "capitalize",
                              }}>
                        {diff}
                      </button>
                    );
                  })}
                </div>
                <p style={{ margin: "6px 0 0", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                  {configDifficulty === "easier"
                    ? "Simpler vocabulary, more scaffolding."
                    : configDifficulty === "harder"
                    ? "More challenging vocabulary, higher cognitive demand."
                    : "Grade-level review."}
                </p>
              </div>
              {/* Phase 4.2 #12: DOK (Webb's Depth of Knowledge) toggle.
                  null = Auto (no DOK directive); 1-4 = explicit cognitive
                  rigor target. Coexists with difficulty (orthogonal —
                  difficulty is vocab/scaffolding tone). */}
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
                  Cognitive demand (DOK)
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {[null, 1, 2, 3, 4].map(function(level) {
                    var active = level === configDok;
                    var label = level === null ? "Auto" : String(level);
                    return (
                      <button key={String(level)}
                              onClick={function() { setConfigDok(level); }}
                              disabled={disabled}
                              style={{
                                flex: "1 1 60px", padding: "8px 12px", fontSize: "0.85rem",
                                borderRadius: "6px", fontWeight: active ? 700 : 500,
                                border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                background: active ? "rgba(99,102,241,0.15)" : "transparent",
                                color: active ? "var(--accent-primary)" : "var(--text-primary)",
                                cursor: disabled ? "not-allowed" : "pointer",
                              }}>
                        {label}
                      </button>
                    );
                  })}
                </div>
                <p style={{ margin: "6px 0 0", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                  {configDok === null
                    ? "AI picks the cognitive level appropriate to the standard."
                    : configDok === 1 ? "DOK 1 — Recall & Reproduction."
                    : configDok === 2 ? "DOK 2 — Skills & Concepts."
                    : configDok === 3 ? "DOK 3 — Strategic Thinking."
                    : "DOK 4 — Extended Thinking."}
                </p>
              </div>
            </div>
          ) : state === "generating" || state === "regenerating" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
              {state === "regenerating" ? "Regenerating..." : ("Generating " + configCount + " practice questions...")}
            </div>
          ) : state === "error" ? (
            <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>
              {error}
              <div style={{ marginTop: "16px" }}>
                <button onClick={regenerateAll} className="btn btn-primary">Retry</button>
              </div>
            </div>
          ) : state === "success" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--success)" }}>
              Published to {nTargets} student{nTargets === 1 ? "" : "s"}.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {/* Phase 4.2 #2: tab strip when personalized. One tab per
                  variant; click to switch the preview pane. */}
              {isPersonalized && (
                <div style={{
                  display: "flex", flexWrap: "wrap", gap: "6px",
                  borderBottom: "1px solid var(--glass-border)", paddingBottom: "8px",
                }}>
                  {variants.map(function(v, vi) {
                    var active = vi === activeVariantIndex;
                    return (
                      <button key={v.student_id || vi}
                              onClick={function() { setActiveVariantIndex(vi); }}
                              disabled={disabled}
                              style={{
                                padding: "6px 12px", fontSize: "0.8rem",
                                borderRadius: "6px",
                                border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                background: active ? "rgba(99,102,241,0.15)" : "transparent",
                                color: active ? "var(--accent-primary)" : "var(--text-primary)",
                                cursor: disabled ? "not-allowed" : "pointer",
                                fontWeight: active ? 700 : 500,
                              }}>
                        {v.student_name || v.student_id}
                      </button>
                    );
                  })}
                </div>
              )}
              {/* Phase 4.2 #1: lesson preview above questions. In personalized
                  mode, show the active variant's lesson; in shared mode, the
                  shared one. */}
              {isPersonalized
                ? (activeVariant && activeVariant.lesson && <LessonBlock lesson={activeVariant.lesson} />)
                : (data && data.lesson && <LessonBlock lesson={data.lesson} />)
              }
              {validationError && (
                <div style={{
                  padding: "10px 14px", borderRadius: "6px",
                  background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                  fontSize: "0.85rem", border: "1px solid var(--danger)",
                }}>
                  {validationError}
                </div>
              )}
              {activeQuestions.map(function(q, idx) {
                return (
                  <QuestionCard key={idx} index={idx} question={q} disabled={disabled}
                                onChange={function(updated) {
                                  setActiveQuestions(function(prev) {
                                    var copy = prev.slice();
                                    copy[idx] = updated;
                                    return copy;
                                  });
                                }} />
                );
              })}
            </div>
          )}
        </div>

        {/* Footer — config state */}
        {state === "config" && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            {/* Phase 4.2 #3 (Codex full-PR MAJOR): Cancel preserves preview
                when prior data exists. Only fully closes when no preview to
                return to (initial open state). */}
            <button
              onClick={function() {
                if (data && (questions.length > 0 || variants.length > 0)) {
                  setState("preview");
                } else {
                  onClose();
                }
              }}
              disabled={disabled}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button onClick={handleGenerate} disabled={disabled} className="btn btn-primary">
              Generate
            </button>
          </div>
        )}

        {/* Footer — preview / publishing state */}
        {(state === "preview" || state === "publishing") && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button onClick={onClose} disabled={disabled} className="btn btn-secondary">Cancel</button>
            {/* Phase 4.2 #3: Adjust settings returns to config state with
                preview state preserved (in case teacher cancels back). */}
            <button onClick={function() { setState("config"); }} disabled={disabled} className="btn btn-secondary">
              Adjust settings
            </button>
            <button onClick={function() { setConfirmRegenOpen(true); }} disabled={disabled} className="btn btn-secondary">
              Regenerate all
            </button>
            <button onClick={publish} disabled={disabled} className="btn btn-primary">
              {state === "publishing" ? "Publishing..." : "Publish to " + nTargets}
            </button>
          </div>
        )}

        {/* Confirm regenerate dialog */}
        {confirmRegenOpen && (
          <div onClick={function() { setConfirmRegenOpen(false); }}
               style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                        zIndex: 9501, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div onClick={function(e) { e.stopPropagation(); }} className="glass-card"
                 style={{ padding: "20px", maxWidth: "400px" }}>
              <h4 style={{ marginTop: 0 }}>Regenerate all questions?</h4>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Any edits you've made will be lost.</p>
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                <button onClick={function() { setConfirmRegenOpen(false); }} className="btn btn-secondary">Keep editing</button>
                <button onClick={regenerateAll} className="btn btn-primary">Regenerate</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function QuestionCard({ index, question, disabled, onChange }) {
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
