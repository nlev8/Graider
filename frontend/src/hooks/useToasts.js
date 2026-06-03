import { useState, useRef } from "react";

/*
 * useToasts — toast-notification state + add/remove handlers, pushed down from the
 * App.jsx shell (App.jsx decomposition, slice 2). Owns the `toasts` list, the id
 * counter ref, and the add (with auto-dismiss) + remove handlers. Handler bodies
 * moved VERBATIM from App.jsx. Self-contained (no args). Returns the list + handlers
 * + the raw `setToasts` (App's grading-status effect mutates a live toast in place).
 *
 * NOTE: the `status.results`-keyed toast-spawn effect stays in App.jsx — it is coupled
 * to the grading `status` state (the useGradingResults cluster) and moving it here would
 * relocate a useEffect across ~40 hooks (an effect-order change). It calls this hook's
 * `addToast` and keeps its own `lastResultCount` ref in App.
 */
export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const toastIdCounter = useRef(0);

  const addToast = (message, type = "success", duration = 4000) => {
    const id = ++toastIdCounter.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    // If duration is 0 or null, toast persists until manually removed
    if (duration) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    }
    return id; // Return ID so caller can remove it later
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return { toasts, setToasts, addToast, removeToast };
}
