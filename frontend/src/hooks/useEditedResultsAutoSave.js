import { useEffect } from "react";
import * as api from "../services/api";

/*
 * useEditedResultsAutoSave — debounced auto-save of inline result edits, pushed down
 * from the App.jsx shell (App.jsx decomposition slice 8). Pure side-effect hook (no
 * state, no return): when editedResults changes, it persists any item flagged `edited`
 * (with a filename) to the backend after a 1s debounce and clears the edited flag on
 * success. Effect body + dep array [editedResults] moved VERBATIM; editedResults and
 * setEditedResults are passed in.
 */
export function useEditedResultsAutoSave({ editedResults, setEditedResults }) {
  // Auto-save edited results to backend (debounced)
  useEffect(() => {
    if (!editedResults.length) return;

    // Find results that have been edited
    const editedItems = editedResults.filter((r) => r.edited && r.filename);
    if (!editedItems.length) return;

    const saveTimeout = setTimeout(async () => {
      for (const item of editedItems) {
        try {
          await api.updateResult(item.filename, {
            score: item.score,
            letter_grade: item.letter_grade,
            feedback: item.feedback,
          });
          // Mark as saved by clearing the edited flag
          setEditedResults((prev) =>
            prev.map((r) =>
              r.filename === item.filename ? { ...r, edited: false } : r
            )
          );
        } catch (error) {
          console.error("Failed to save result:", error);
        }
      }
    }, 1000); // 1 second debounce

    return () => clearTimeout(saveTimeout);
  }, [editedResults]);
}
