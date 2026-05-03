/**
 * PublishedAssessmentModal — confirmation/success modal shown after a
 * teacher publishes content. Displays the join code, the share link
 * (with a copy-to-clipboard button), and a short usage cheatsheet
 * branched on whether the publish was class-based or anonymous-join.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `publishedAssessmentModal.show`. Lifted as a presentational component;
 * App.jsx still owns the underlying `publishedAssessmentModal` state
 * object and the `addToast` helper.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   joinCode: string
 *   joinLink: string
 *   isClassBased: bool — switches the displayed label + instructions
 *   onCopied: () => void — invoked after `navigator.clipboard.writeText`
 *                          succeeds (App typically pipes this to a toast)
 *   title?: string — header text, default "Published!"
 *   subtitle?: string — body text below the header, default
 *                       "Students can now access this using the code below."
 */
import React from "react";
import Icon from "./Icon";

export default function PublishedAssessmentModal({
  open,
  onClose,
  joinCode,
  joinLink,
  isClassBased,
  onCopied,
  title = "Published!",
  subtitle = "Students can now access this using the code below.",
}) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.8)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#1a1a2e",
          borderRadius: "16px",
          padding: "30px",
          maxWidth: "500px",
          width: "100%",
          textAlign: "center",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div style={{ marginBottom: "20px" }}>
          <Icon name="CheckCircle" size={48} style={{ color: "#22c55e" }} />
        </div>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "10px" }}>
          {title}
        </h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: "25px" }}>
          {subtitle}
        </p>

        {/* Join Code Display */}
        <div
          style={{
            background: "linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(99, 102, 241, 0.2))",
            border: "2px solid var(--accent-primary)",
            borderRadius: "12px",
            padding: "20px",
            marginBottom: "20px",
          }}
        >
          <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
            {isClassBased ? "Class Code" : "Join Code"}
          </div>
          <div
            style={{
              fontSize: "2.5rem",
              fontWeight: 800,
              letterSpacing: "0.15em",
              fontFamily: "monospace",
              color: "var(--accent-primary)",
            }}
          >
            {joinCode}
          </div>
        </div>

        {/* Link */}
        <div style={{ marginBottom: "25px" }}>
          <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
            {isClassBased ? "Student portal link:" : "Or share this link:"}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background: "var(--glass-bg)",
              padding: "12px 15px",
              borderRadius: "8px",
            }}
          >
            <input
              type="text"
              readOnly
              value={joinLink}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                color: "var(--text-primary)",
                fontSize: "0.9rem",
                outline: "none",
              }}
            />
            <button
              onClick={() => {
                navigator.clipboard.writeText(joinLink);
                if (onCopied) onCopied();
              }}
              className="btn btn-secondary"
              style={{ padding: "8px 12px" }}
            >
              <Icon name="Copy" size={16} />
            </button>
          </div>
        </div>

        {/* Instructions */}
        <div
          style={{
            background: "rgba(34, 197, 94, 0.1)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            borderRadius: "8px",
            padding: "15px",
            marginBottom: "25px",
            textAlign: "left",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "8px", color: "#22c55e" }}>
            <Icon name="Info" size={16} style={{ marginRight: "8px" }} />
            How students access this:
          </div>
          {isClassBased ? (
            <ol style={{ margin: 0, paddingLeft: "20px", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              <li>Go to <strong>app.graider.live/student</strong></li>
              <li>Log in with school email + class code: <strong>{joinCode}</strong></li>
              <li>Find the assignment on their dashboard</li>
            </ol>
          ) : (
            <ol style={{ margin: 0, paddingLeft: "20px", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              <li>Go to <strong>app.graider.live/join</strong></li>
              <li>Enter code: <strong>{joinCode}</strong></li>
              <li>Enter their name and start</li>
            </ol>
          )}
        </div>

        <button
          onClick={onClose}
          className="btn btn-primary"
          style={{ padding: "12px 30px" }}
        >
          Done
        </button>
      </div>
    </div>
  );
}
