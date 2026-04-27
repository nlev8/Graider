import React, { useState, useEffect, useRef } from "react";
import * as api from "../services/api";

/**
 * Phase 4 — Remediation Drawer.
 *
 * State machine: idle → generating → preview → (regenerating | publishing) → success | error
 */
export default function RemediationDrawer({
  open, onClose, classId, standardCode, targetMode, targetStudentId, targetStudentName,
  onPublished,
}) {
  var [state, setState] = useState("idle");
  var [error, setError] = useState(null);
  var [data, setData] = useState(null);  // {questions, target_student_ids, ...}
  var [questions, setQuestions] = useState([]);
  var [confirmRegenOpen, setConfirmRegenOpen] = useState(false);
  // Validation error is shown inline in the preview state (not the error state).
  // Separate state slot so the drawer doesn't drop into the full-screen "error"
  // path (which is reserved for network/server errors).
  var [validationError, setValidationError] = useState(null);
  var cancelRef = useRef({ cancelled: false });
  var successTimerRef = useRef(null);

  // Reset on open / close.
  useEffect(function() {
    if (!open) {
      cancelRef.current.cancelled = true;
      if (successTimerRef.current) { clearTimeout(successTimerRef.current); successTimerRef.current = null; }
      return;
    }
    cancelRef.current = { cancelled: false };
    setState("generating");
    setError(null);
    setData(null);
    setQuestions([]);
    setValidationError(null);  // clear on every fresh open (defensive even though parent unmounts on close)
    var payload = { standard_code: standardCode, target_mode: targetMode };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Generation failed");
          setState("error");
          return;
        }
        setData(res);
        setQuestions(res.questions || []);
        setState("preview");
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
    return function() { cancelRef.current.cancelled = true; };
  }, [open, classId, standardCode, targetMode, targetStudentId]);

  // Esc to close.
  useEffect(function() {
    if (!open) return;
    function handler(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", handler);
    return function() { document.removeEventListener("keydown", handler); };
  }, [open, onClose]);

  function regenerateAll() {
    setConfirmRegenOpen(false);
    setValidationError(null);  // clear any stale validation message before regen
    setState("regenerating");
    var payload = { standard_code: standardCode, target_mode: targetMode };
    if (targetMode === "single_student") payload.target_student_id = targetStudentId;
    api.postRemediate(classId, payload)
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Regeneration failed");
          setState("error");
          return;
        }
        setData(res);
        setQuestions(res.questions || []);
        setState("preview");
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  // Pre-publish validation. Returns null on success, error string on failure.
  // Verifies: ≥1 question, every question has non-empty text, MC has ≥2
  // non-empty choices AND correct_answer references one of those choices.
  // The remediation prompt allows the AI to mark the correct answer as
  // a letter ("A"/"B"/"C"/"D"), the choice text, OR a numeric index — the
  // validator accepts all three forms.
  function validateBeforePublish() {
    if (questions.length < 1) return "At least one question required";
    for (var i = 0; i < questions.length; i++) {
      var q = questions[i];
      if (!q.text || !q.text.trim()) return "Question " + (i + 1) + " has no text";
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
        if (nonEmptyChoices.length < 2) return "Question " + (i + 1) + " needs at least 2 choices";
        var correct = q.correct_answer != null ? q.correct_answer : q.answer;
        if (correct == null || correct === "") return "Question " + (i + 1) + " has no correct answer";
        var matched = false;
        // (a) numeric index match
        if (typeof correct === "number") {
          matched = nonEmptyChoices.some(function(c) { return c.index === correct; });
        }
        if (!matched) {
          var s = String(correct).trim();
          // (b) string numeric index ("0".."N")
          if (/^[0-9]+$/.test(s)) {
            var idx = parseInt(s, 10);
            matched = nonEmptyChoices.some(function(c) { return c.index === idx; });
          }
          // (c) letter A-Z (case-insensitive) — A=0, B=1, etc.
          if (!matched && /^[A-Za-z]$/.test(s)) {
            var letterIdx = s.toUpperCase().charCodeAt(0) - 65;
            matched = nonEmptyChoices.some(function(c) { return c.index === letterIdx; });
          }
          // (d) exact choice text match
          if (!matched) {
            matched = nonEmptyChoices.some(function(c) { return c.label === s; });
          }
        }
        if (!matched) {
          return "Question " + (i + 1) + " correct answer doesn't match any choice";
        }
      }
    }
    return null;
  }

  function publish() {
    var ve = validateBeforePublish();
    if (ve) { setValidationError(ve); return; }
    setValidationError(null);
    setState("publishing");
    api.publishToClass(
      classId,
      { questions: questions },
      "assessment",
      "Remediation: " + standardCode,
      {},  // settings — leave default
      null,  // dueDate — none
      data.target_student_ids,
    )
      .then(function(res) {
        if (cancelRef.current.cancelled) return;
        if (!res || res.error) {
          setError((res && (res.detail || res.error)) || "Publish failed");
          setState("error");
          return;
        }
        setState("success");
        if (onPublished) onPublished();
        successTimerRef.current = setTimeout(function() {
          if (!cancelRef.current.cancelled) onClose();
        }, 2000);
      })
      .catch(function(e) {
        if (cancelRef.current.cancelled) return;
        setError((e && e.message) || "Network error");
        setState("error");
      });
  }

  if (!open) return null;

  var disabled = state === "generating" || state === "regenerating" || state === "publishing";
  var nTargets = data && data.target_student_ids ? data.target_student_ids.length : 0;
  var subtitle = "";
  if (targetMode === "single_student") {
    subtitle = "for " + (targetStudentName || "student");
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
          {state === "generating" || state === "regenerating" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
              {state === "regenerating" ? "Regenerating..." : "Generating 8 practice questions..."}
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
              {validationError && (
                <div style={{
                  padding: "10px 14px", borderRadius: "6px",
                  background: "rgba(239,68,68,0.15)", color: "var(--danger)",
                  fontSize: "0.85rem", border: "1px solid var(--danger)",
                }}>
                  {validationError}
                </div>
              )}
              {questions.map(function(q, idx) {
                return (
                  <QuestionCard key={idx} index={idx} question={q} disabled={disabled}
                                onChange={function(updated) {
                                  var copy = questions.slice();
                                  copy[idx] = updated;
                                  setQuestions(copy);
                                }} />
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        {(state === "preview" || state === "publishing") && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            <button onClick={onClose} disabled={disabled} className="btn btn-secondary">Cancel</button>
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
