import { useEffect, useRef, useMemo } from "react";
import { useEditedResultsAutoSave } from "../hooks/useEditedResultsAutoSave";

/*
 * useAppResultsSync — segment 5 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 1316-1438: the
 * email-approvals re-index effect (filename-keyed survival across re-grades),
 * the grades-approved reset, the editedResults ⟷ status.results sync,
 * useEditedResultsAutoSave, the graded-toast effect (consumes the
 * lastResultCount ref owned by useAppCoreState — the pre-split coupling
 * comment at App.jsx 685-690 explains why they live apart), and the
 * sortedPeriods memo. Effect order within the segment is byte-identical;
 * useEditedResultsAutoSave stays BETWEEN the sync effect and the graded-toast
 * effect exactly as on main.
 * See useAppCoreState for the hook-order contract.
 */
export function useAppResultsSync(ctx) {
  const {
    addToast, config, editedResults, lastResultCount, periods, setEditedResults, setEmailApprovals,
    setGradesApproved, status,
  } = ctx;

  // Auto-scroll log + auto-expand-on-error effects moved into tabs/GradeTab.jsx
  // (with logRef and showActivityLog state) in PR 2 of the Grade tab extraction sprint.

  // Load email approvals from persisted results AND re-index when results change.
  // emailApprovals is keyed by array index. When re-grading, the backend removes
  // the old result and appends the new one at the end, shifting all indices.
  // This effect rebuilds the index mapping by matching filenames so approvals
  // follow the correct results even when indices change.
  const prevResultsRef = useRef([]);
  useEffect(() => {
    if (status.results.length > 0) {
      const prevResults = prevResultsRef.current;
      const loadedApprovals = {};
      status.results.forEach((r, idx) => {
        if (r.email_approval) {
          loadedApprovals[idx] = r.email_approval;
        }
      });
      setEmailApprovals((prev) => {
        // Build filename → approval from previous state + previous results
        var fileApprovals = {};
        prevResults.forEach(function(r, oldIdx) {
          if (prev[oldIdx]) fileApprovals[r.filename] = prev[oldIdx];
        });
        // Rebuild index-based mapping for current results
        var reindexed = {};
        status.results.forEach(function(r, newIdx) {
          if (loadedApprovals[newIdx]) {
            // Persisted approval on the result itself takes priority
            reindexed[newIdx] = loadedApprovals[newIdx];
          } else if (fileApprovals[r.filename]) {
            // Carry over approval from previous state by filename
            reindexed[newIdx] = fileApprovals[r.filename];
          }
        });
        return reindexed;
      });
    }
    prevResultsRef.current = status.results.map(function(r) { return { filename: r.filename }; });
  }, [status.results]); // Run on every results change, not just length

  // Reset approval gate when new results come in
  useEffect(() => {
    setGradesApproved(false);
  }, [status.results.length]);

  // Sync editedResults with status.results (preserve user edits)
  useEffect(() => {
    if (status.results.length === 0) {
      setEditedResults([]);
      return;
    }
    setEditedResults((prev) => {
      // If same length, merge new data but preserve edits
      if (prev.length === status.results.length) {
        return prev.map((edited, i) => {
          if (edited.edited) {
            return { ...status.results[i], ...edited, edited: true };
          }
          return { ...status.results[i], edited: false };
        });
      }
      // Length changed (results added or deleted) — rebuild from status.results
      // preserving any user edits by matching on filename
      var editMap = {};
      prev.forEach(function(er) {
        if (er.edited) editMap[er.filename] = er;
      });
      return status.results.map(function(r) {
        var existing = editMap[r.filename];
        if (existing) return { ...r, ...existing, edited: true };
        return { ...r, edited: false };
      });
    });
  }, [status.results]);

  // Edited-results auto-save extracted to useEditedResultsAutoSave (decomp slice 8).
  useEditedResultsAutoSave({ editedResults, setEditedResults });

  // Show toast when new assignments are graded
  useEffect(() => {
    const currentCount = status.results.length;
    if (
      config.showToastNotifications &&
      currentCount > lastResultCount.current &&
      lastResultCount.current > 0
    ) {
      const newResults = status.results.slice(lastResultCount.current);
      newResults.forEach((result) => {
        const grade = result.letter_grade || "N/A";
        const score = result.score !== undefined ? `${result.score}%` : "";
        addToast(
          `Graded - ${result.student_name}: ${grade} ${score}`,
          grade === "A" || grade === "B"
            ? "success"
            : grade === "C"
              ? "info"
              : "warning",
        );
      });
    }
    lastResultCount.current = currentCount;
  }, [status.results, config.showToastNotifications]);

  // PR 4 deleted the dead portal-era loadAvailableFiles no-op and the unused
  // fileMatchesPeriodStudent + stripNamePunctuation helpers. AnalyticsTab has
  // its own independent local copy of stripNamePunctuation that still works.
  // loadPeriodStudents was already moved into tabs/GradeTab.jsx in PR 3.

  // Sort periods numerically by extracting number from period_name (e.g., "Period 1" → 1)
  const sortedPeriods = useMemo(() => {
    return [...periods].sort((a, b) => {
      const numA = parseInt(
        (a.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      const numB = parseInt(
        (b.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      return numA - numB;
    });
  }, [periods]);

  return {
    prevResultsRef, sortedPeriods,
  };
}
