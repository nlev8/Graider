/**
 * ActivityLog — collapsible monospace log panel that shows the most
 * recent (up to 30) lines of grading activity. App.jsx attaches a ref
 * to the scrollable div for auto-scrolling, so this component uses
 * `React.forwardRef` to keep that wiring intact.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showActivityLog`. Presentational; renders the empty state when the
 * log is empty and slices to the last 30 entries otherwise.
 *
 * Props:
 *   open: bool
 *   log: string[]  — full activity log (component slices the last 30)
 *
 * Forwarded ref: attached to the scrollable container div, so callers
 *                that need to programmatically scroll (e.g. to the
 *                bottom on each new line) can keep doing so.
 */
import React from "react";

const ActivityLog = React.forwardRef(function ActivityLog({ open, log }, ref) {
  if (!open) return null;

  return (
    <div
      ref={ref}
      style={{
        marginTop: "15px",
        maxHeight: "200px",
        overflowY: "auto",
        background: "var(--input-bg)",
        borderRadius: "10px",
        padding: "15px",
        fontFamily: "Monaco, Consolas, monospace",
        fontSize: "0.8rem",
        lineHeight: "1.6",
      }}
    >
      {log.length === 0 ? (
        <p
          style={{
            color: "var(--text-muted)",
            margin: 0,
            textAlign: "center",
          }}
        >
          Ready to grade. Activity will appear here...
        </p>
      ) : (
        log.slice(-30).map((line, i) => (
          <div
            key={i}
            style={{
              marginBottom: "4px",
              color: "var(--text-secondary)",
            }}
          >
            {line}
          </div>
        ))
      )}
    </div>
  );
});

export default ActivityLog;
