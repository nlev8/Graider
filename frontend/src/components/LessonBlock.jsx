import React from "react";
import { renderQuestionText } from "../utils/renderLatex";

/**
 * Phase 4.2 #1 — LessonBlock: renders the AI-generated mini-lesson at the top
 * of a remediation assessment. Three labeled sections: Intro, Worked Example,
 * Key Takeaway.
 *
 * Spec: docs/superpowers/specs/2026-04-29-phase4.2-lesson-text-design.md
 *
 * Math rendering: prose runs through `renderQuestionText`, which returns an
 * HTML string (escaped prose + KaTeX HTML). Renders via `dangerouslySetInnerHTML`.
 * Safety: prose is escaped by `escapeHtml`; KaTeX uses `throwOnError: false`.
 *
 * KaTeX delimiters: \(...\) inline, \[...\] display. NOT $...$ (renderLatex.js:6-13
 * explicitly does not support dollar signs).
 */
function paragraphsFor(field) {
  if (!field || typeof field !== "string") return [];
  // CRLF-safe: strip \r before splitting on \n.
  var stripped = field.split(String.fromCharCode(13)).join("");
  var parts = stripped.split(String.fromCharCode(10));
  // Drop empty/whitespace-only paragraphs.
  return parts.map(function(p) { return p.trim(); }).filter(function(p) { return p.length > 0; });
}

function LessonSection({ label, body }) {
  var paragraphs = paragraphsFor(body);
  if (paragraphs.length === 0) return null;
  return (
    <div style={{ marginBottom: "16px" }}>
      <div style={{
        fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase",
        letterSpacing: "0.05em", color: "var(--accent-primary)", marginBottom: "6px",
      }}>{label}</div>
      {paragraphs.map(function(p, idx) {
        return (
          <div
            key={idx}
            style={{ fontSize: "0.95rem", lineHeight: "1.6", marginBottom: "8px", color: "var(--text-primary)" }}
            dangerouslySetInnerHTML={{ __html: renderQuestionText(p) }}
          />
        );
      })}
    </div>
  );
}

export default function LessonBlock({ lesson }) {
  if (!lesson || typeof lesson !== "object") return null;
  var intro = lesson.intro;
  var workedExample = lesson.worked_example;
  var keyTakeaway = lesson.key_takeaway;
  // If all three fields are missing/empty, render nothing.
  if (!intro && !workedExample && !keyTakeaway) return null;
  return (
    <div className="glass-card" style={{
      padding: "20px", marginBottom: "20px",
      borderLeft: "3px solid var(--accent-primary)",
    }}>
      <LessonSection label="Intro" body={intro} />
      <LessonSection label="Worked Example" body={workedExample} />
      <LessonSection label="Key Takeaway" body={keyTakeaway} />
    </div>
  );
}
