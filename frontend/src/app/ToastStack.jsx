import React from "react";
import Icon from "../components/Icon";

/*
 * ToastStack — the fixed top-right toast notification stack, relocated
 * VERBATIM from App.jsx 2816-2911 in the finale split. State stays in
 * useToasts (via useAppCoreState); this is purely the render.
 */
export default function ToastStack(props) {
  const {
    removeToast, toasts,
  } = props;

  return (
      <div
        style={{
          position: "fixed",
          top: "20px",
          right: "20px",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          maxWidth: "350px",
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-card fade-in"
            style={{
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background:
                toast.type === "success"
                  ? "rgba(74,222,128,0.15)"
                  : toast.type === "warning"
                    ? "rgba(251,191,36,0.15)"
                    : toast.type === "error"
                      ? "rgba(248,113,113,0.15)"
                      : "rgba(96,165,250,0.15)",
              border: `1px solid ${
                toast.type === "success"
                  ? "rgba(74,222,128,0.4)"
                  : toast.type === "warning"
                    ? "rgba(251,191,36,0.4)"
                    : toast.type === "error"
                      ? "rgba(248,113,113,0.4)"
                      : "rgba(96,165,250,0.4)"
              }`,
              boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            }}
          >
            <Icon
              name={
                toast.type === "success"
                  ? "CheckCircle"
                  : toast.type === "warning"
                    ? "AlertTriangle"
                    : toast.type === "error"
                      ? "XCircle"
                      : "Info"
              }
              size={18}
              style={{
                color:
                  toast.type === "success"
                    ? "#4ade80"
                    : toast.type === "warning"
                      ? "#fbbf24"
                      : toast.type === "error"
                        ? "#f87171"
                        : "#60a5fa",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: "0.9rem",
                color: "var(--text-primary)",
                flex: 1,
              }}
            >
              {toast.message}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeToast(toast.id);
              }}
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "4px 6px",
                color: "var(--text-secondary)",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="X" size={16} />
            </button>
          </div>
        ))}
      </div>
  );
}
