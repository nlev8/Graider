import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/**
 * Clear Results button extracted from ResultsFilterControls (CQ wave-3 split).
 * Handles the "Clear Filtered" / "Clear All" action inline — reads filter state
 * to determine which results are visible, then calls api.clearResults and updates
 * parent state via the passed setters. Pure-prop: no new fetches, no effects.
 */
export default function ResultsClearButton({
  resultsFilter,
  resultsPeriodFilter,
  resultsAssignmentFilter,
  resultsSearch,
  status,
  emailApprovals,
  setStatus,
  setEditedResults,
  setEmailApprovals,
  setEditedEmails,
  addToast,
}) {
  const hasAnyFilter =
    resultsFilter !== "all" ||
    resultsPeriodFilter ||
    resultsAssignmentFilter ||
    resultsSearch.trim();

  return (
    <button
      onClick={async () => {
        const hasFilter =
          resultsFilter !== "all" ||
          resultsPeriodFilter ||
          resultsAssignmentFilter ||
          resultsSearch.trim();

        // Collect filenames of currently visible results
        const visibleFilenames = [];
        const searchLower = resultsSearch.trim().toLowerCase();
        status.results.forEach((r, idx) => {
          if (resultsFilter === "handwritten" && !r.is_handwritten) return;
          if (resultsFilter === "typed" && r.is_handwritten) return;
          if (resultsFilter === "verified" && r.marker_status !== "verified") return;
          if (resultsFilter === "unverified" && r.marker_status !== "unverified") return;
          if (resultsFilter === "mismatched" && !r.config_mismatch) return;
          if (resultsFilter === "resubmission" && !r.is_resubmission) return;
          if (resultsFilter === "approved" && emailApprovals[idx] !== "approved") return;
          if (resultsFilter === "unapproved" && emailApprovals[idx] === "approved") return;
          if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
          if (
            resultsAssignmentFilter &&
            (r.assignment || r.filename) !== resultsAssignmentFilter
          )
            return;
          if (
            searchLower &&
            !(
              (r.student_name || "").toLowerCase().includes(searchLower) ||
              (r.assignment || "").toLowerCase().includes(searchLower)
            )
          )
            return;
          if (r.filename) visibleFilenames.push(r.filename);
        });

        const clearCount = hasFilter
          ? visibleFilenames.length
          : status.results.length;
        const confirmMsg = hasFilter
          ? "Clear " + clearCount + " filtered results? This cannot be undone."
          : "Clear all " + clearCount + " grading results? This cannot be undone.";

        if (confirm(confirmMsg)) {
          try {
            if (hasFilter && visibleFilenames.length > 0) {
              // Clear only the visible results by filename
              await api.clearResults(visibleFilenames);
              const filenameSet = new Set(visibleFilenames);
              setStatus((prev) => ({
                ...prev,
                results: prev.results.filter((r) => !filenameSet.has(r.filename)),
              }));
              setEditedResults((prev) =>
                prev.filter((r) => !filenameSet.has(r.filename))
              );
              // Clear approvals/emails for removed results
              const removedIndices = new Set();
              status.results.forEach((r, i) => {
                if (filenameSet.has(r.filename)) removedIndices.add(i);
              });
              setEmailApprovals((prev) => {
                const updated = { ...prev };
                removedIndices.forEach((i) => delete updated[i]);
                return updated;
              });
              setEditedEmails((prev) => {
                const updated = { ...prev };
                removedIndices.forEach((i) => delete updated[i]);
                return updated;
              });
              addToast("Cleared " + visibleFilenames.length + " results", "success");
            } else if (!hasFilter) {
              // Clear everything
              await api.clearResults();
              setStatus((prev) => ({
                ...prev,
                results: [],
                log: [],
                complete: false,
              }));
              setEditedResults([]);
              setEmailApprovals({});
              setEditedEmails({});
              addToast("Cleared all results", "success");
            }
          } catch (e) {
            addToast("Error clearing results: " + e.message, "error");
          }
        }
      }}
      className="btn btn-secondary"
      style={{ background: "rgba(239,68,68,0.2)" }}
    >
      <Icon name="Trash2" size={18} />
      {hasAnyFilter ? "Clear Filtered" : "Clear All"}
    </button>
  );
}
