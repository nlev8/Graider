/**
 * AttemptDrawer — right-side drawer that lists every submission attempt
 * a student has made for the current published assessment, with
 * timestamp, time-taken, percentage, and points scored.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by truthy
 * `attemptDrawerStudent`. Pure presentational; only depends on the
 * student object.
 *
 * Props:
 *   student: { student_name, attempts: Array<{ submission_id,
 *              attempt_number, percentage?, score?, total_points?,
 *              submitted_at?, time_taken_seconds? }> } | null
 *   onClose: () => void
 */
import React from "react";

export default function AttemptDrawer({ student, onClose }) {
  if (!student) return null;

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "var(--modal-bg)", display: "flex", alignItems: "center",
        justifyContent: "flex-end", zIndex: 9998, padding: "20px",
      }}
      onClick={() => onClose()}
    >
      <div
        className="glass-card"
        style={{ width: "100%", maxWidth: "500px", maxHeight: "90vh", overflowY: "auto", padding: "24px", borderRadius: "16px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
            {student.student_name}
          </h3>
          <button
            onClick={() => onClose()}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}
          >
            {String.fromCharCode(10005)}
          </button>
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
          {student.attempts.length} attempts
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {student.attempts.map((a) => {
            const submittedDate = a.submitted_at ? new Date(a.submitted_at).toLocaleString() : String.fromCharCode(8212);
            const timeMin = a.time_taken_seconds ? Math.floor(a.time_taken_seconds / 60) + 'm ' + (a.time_taken_seconds % 60) + 's' : String.fromCharCode(8212);
            const pct = a.percentage != null ? Math.round(a.percentage) + '%' : String.fromCharCode(8212);
            return (
              <div key={a.submission_id} style={{ padding: "12px 14px", borderRadius: "10px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>Attempt {a.attempt_number}</div>
                  <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{pct}</div>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  Submitted {submittedDate} {String.fromCharCode(8226)} {timeMin}
                </div>
                {a.score != null && (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                    Score: {a.score} / {a.total_points}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
