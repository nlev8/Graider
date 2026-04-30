import React from "react";

/**
 * Phase 4.2 #7 — Renders pills under a Gradebook column header (or in the
 * SubmissionDetail drawer header) when the content is a remediation.
 *
 * Spec: docs/superpowers/specs/2026-04-29-phase4.2-gradebook-remediation-badge-design.md
 *
 * Two pills:
 *   - "Remediation" (always, when target_student_ids is a non-empty array)
 *   - "Recalled" (when remediation AND is_active === false)
 *
 * Style values match the existing dashboard recall badge in
 * RemediationEffectiveness.jsx exactly (Phase 4.2 #5 visual consistency).
 *
 * Defensive predicate: tightened from the backend's "is not None" contract
 * to "non-empty array" so legacy/cached responses with undefined fields
 * don't render phantom badges, AND so a defensive UI handles `[]` even
 * though publish_to_class rejects empty arrays at write time.
 */

function isRemediation(item) {
  return Array.isArray(item && item.target_student_ids) &&
         item.target_student_ids.length > 0;
}

function isRecalled(item) {
  return isRemediation(item) && item.is_active === false;
}

export default function RemediationBadges({ item }) {
  if (!isRemediation(item)) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", justifyContent: "center" }}>
      <span style={{
        fontSize: "0.78rem", padding: "3px 10px", borderRadius: "6px",
        background: "rgba(99,102,241,0.15)", color: "var(--accent-primary)", fontWeight: 700,
      }}>Remediation</span>
      {isRecalled(item) && (
        <span style={{
          fontSize: "0.78rem", padding: "3px 10px", borderRadius: "6px",
          background: "rgba(239,68,68,0.12)", color: "var(--danger)", fontWeight: 700,
        }}>Recalled</span>
      )}
    </div>
  );
}
