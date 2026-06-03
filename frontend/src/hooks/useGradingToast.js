import { useEffect, useRef } from "react";
import { track as phTrack } from "../services/posthog";

/*
 * useGradingToast — the persistent "Grading in progress…" toast lifecycle, pushed down
 * from the App.jsx shell (App.jsx decomposition slice 7). Pure side-effect hook (owns
 * its two tracking refs, returns nothing): shows a persistent toast when a grading job
 * starts, updates it with the current file, and on completion removes it and emits the
 * completion / cost-limit / resubmission toasts plus the grading_completed analytics
 * event. The two refs + effect body + dep array moved VERBATIM; the status/config/
 * isLocalhost values and the toast handlers (addToast/setToasts/removeToast) are passed in.
 */
export function useGradingToast({ status, config, isLocalhost, addToast, setToasts, removeToast }) {
  // Persistent grading toast
  const gradingToastId = useRef(null);
  const wasGrading = useRef(false);

  useEffect(() => {
    if (status.is_running && !wasGrading.current) {
      // Grading just started - show persistent toast
      wasGrading.current = true;
      gradingToastId.current = addToast(
        `Grading in progress... ${status.current_file || ''}`,
        "info",
        0 // persistent
      );
    } else if (status.is_running && gradingToastId.current) {
      // Update the toast message with current file
      setToasts(prev => prev.map(t =>
        t.id === gradingToastId.current
          ? { ...t, message: `Grading: ${status.current_file || 'Processing...'}` }
          : t
      ));
    } else if (!status.is_running && wasGrading.current) {
      // Track grading completion
      if (!isLocalhost && status.results) {
        phTrack('grading_completed', {
          result_count: status.results.length,
          cost: status.session_cost?.total_cost || 0,
          cost_limit_hit: !!status.cost_limit_hit,
        });
      }
      // Grading just finished - remove persistent toast
      wasGrading.current = false;
      if (gradingToastId.current) {
        removeToast(gradingToastId.current);
        gradingToastId.current = null;
      }
      if (status.cost_limit_hit) {
        addToast("Grading auto-stopped: cost limit of $" + (config.cost_limit_per_session || 0).toFixed(2) + " reached. Progress saved.", "warning", 8000);
      }
      if (status.results && status.results.length > 0) {
        const costStr = status.session_cost?.total_cost > 0 ? ` (API cost: $${status.session_cost.total_cost.toFixed(4)})` : "";
        addToast(`Grading complete! ${status.results.length} assignments graded.${costStr}`, "success");
        // Resubmission summary notification
        const resubCount = status.results.filter(r => r.is_resubmission).length;
        if (resubCount > 0) {
          const keptCount = status.results.filter(r => r.is_resubmission && r.kept_higher).length;
          const improvedCount = resubCount - keptCount;
          let msg = resubCount + " resubmission(s) detected.";
          if (improvedCount > 0) msg += " " + improvedCount + " improved.";
          if (keptCount > 0) msg += " " + keptCount + " kept original (higher) grade.";
          addToast(msg, "info", 8000);
        }
      }
    }
  }, [status.is_running, status.current_file, status.results]);
}
