import React from "react";
import Icon from "../../components/Icon";
import ActivityLog from "../../components/ActivityLog";

/*
 * Activity Monitor — horizontal collapsible card; relocated verbatim from
 * GradeTab.jsx (CQ wave-2 split). showActivityLog + logRef stay GradeTab-owned
 * (the auto-scroll and auto-expand-on-error effects in the shell drive them),
 * so the effect lifecycles are byte-identical to the pre-split component.
 */
export default function ActivityMonitorCard({
  status,
  showActivityLog,
  setShowActivityLog,
  logRef,
}) {
  return (
    <div
      className="glass-card"
      style={{
        padding: "15px 20px",
        marginBottom: "20px",
        background: status.error
          ? "rgba(248,113,113,0.05)"
          : status.is_running
            ? "rgba(74,222,128,0.05)"
            : "var(--glass-bg)",
        border: `1px solid ${
          status.error
            ? "rgba(248,113,113,0.3)"
            : status.is_running
              ? "rgba(74,222,128,0.3)"
              : "var(--glass-border)"
        }`,
      }}
    >
      <button
        onClick={() => setShowActivityLog(!showActivityLog)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--text-primary)",
          padding: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Icon
            name={status.error ? "AlertCircle" : "Terminal"}
            size={18}
            style={{
              color: status.error
                ? "#f87171"
                : status.is_running
                  ? "#4ade80"
                  : "var(--text-secondary)",
            }}
          />
          <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
            Activity Monitor
          </span>
          {status.error && (
            <span
              style={{
                fontSize: "0.75rem",
                padding: "3px 10px",
                borderRadius: "12px",
                background: "rgba(248,113,113,0.2)",
                color: "#f87171",
                fontWeight: 500,
              }}
            >
              Error
            </span>
          )}
          {status.is_running && !status.error && (
            <span
              style={{
                fontSize: "0.75rem",
                padding: "3px 10px",
                borderRadius: "12px",
                background: "rgba(74,222,128,0.2)",
                color: "#4ade80",
                fontWeight: 500,
              }}
            >
              Running...
            </span>
          )}
          {status.log.length > 0 && (
            <span
              style={{
                fontSize: "0.75rem",
                padding: "3px 8px",
                borderRadius: "8px",
                background: "var(--input-bg)",
                color: "var(--text-muted)",
              }}
            >
              {status.log.length} entries
            </span>
          )}
        </div>
        <Icon
          name={showActivityLog ? "ChevronUp" : "ChevronDown"}
          size={18}
          style={{ color: "var(--text-muted)" }}
        />
      </button>

      <ActivityLog
        ref={logRef}
        open={showActivityLog}
        log={status.log}
      />
    </div>
  );
}
