import { useEffect } from "react";
import * as api from "../services/api";

/*
 * useAssignmentAutoSave — the debounced Builder-assignment auto-save side effect,
 * pushed down from the App.jsx shell (App.jsx decomposition slice 5). Pure side-effect
 * hook (owns no state, returns nothing), mirroring the existing useSettingsAutoSave:
 * when the Builder assignment / importedDoc change after the initial settings load, it
 * debounce-saves to the backend, handling rename->alias bookkeeping and the post-load
 * skip. The effect body + dep array moved VERBATIM; everything it reads or writes that
 * it does not own (state values, setters, the skip ref, addToast) is passed in.
 */
export function useAssignmentAutoSave({
  assignment,
  setAssignment,
  importedDoc,
  settingsLoaded,
  loadedAssignmentName,
  setLoadedAssignmentName,
  isLoadingAssignment,
  skipAutoSaveRef,
  setSavedAssignments,
  setSavedAssignmentData,
  addToast,
}) {
  // Auto-save Builder assignment when it changes (debounced)
  useEffect(() => {
    if (!settingsLoaded) return;
    if (!assignment.title) return; // Don't save assignments without a title
    if (isLoadingAssignment) return; // Don't save while loading an assignment
    // Skip auto-save right after loading — data is already on disk
    if (skipAutoSaveRef.current) {
      skipAutoSaveRef.current = false;
      return;
    }

    const saveTimeout = setTimeout(async () => {
      // Double-check we're not in the middle of loading
      if (isLoadingAssignment) return;

      try {
        let dataToSave = { ...assignment, importedDoc };
        // Compare sanitized names to detect real renames (not just special-char differences)
        // Backend sanitizes titles to filenames by keeping only [a-zA-Z0-9 \-_]
        const sanitizeForFilename = (s) => s.replace(/[^a-zA-Z0-9 \-_]/g, '').trim();
        const isRename =
          loadedAssignmentName && sanitizeForFilename(loadedAssignmentName) !== sanitizeForFilename(assignment.title);

        // If title changed from a previously loaded assignment, add old name to aliases
        if (isRename) {
          const currentAliases = assignment.aliases || [];
          if (!currentAliases.includes(loadedAssignmentName)) {
            dataToSave.aliases = [...currentAliases, loadedAssignmentName];
            // Also update local state with new alias
            setAssignment((prev) => ({ ...prev, aliases: dataToSave.aliases }));
          }
        }

        const saveResult = await api.saveAssignmentConfig(dataToSave);

        // Only proceed if save was successful
        if (saveResult.status === "saved") {
          // If renamed, delete the old assignment file (alias is preserved in new file)
          if (isRename) {
            try {
              await api.deleteAssignment(loadedAssignmentName);
              console.log(`Renamed assignment: "${loadedAssignmentName}" → "${assignment.title}" (old name saved as alias)`);
            } catch (deleteErr) {
              console.error("Failed to delete old assignment file:", deleteErr);
              // Don't fail the whole operation if delete fails
            }
          }

          if (isRename) {
            // Full list refresh on rename (list structure changed)
            const list = await api.listAssignments();
            if (list.assignments) setSavedAssignments(list.assignments);
            if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
          } else {
            // Normal save — update this card's data locally without full refresh
            const cardKey = sanitizeForFilename(assignment.title);
            setSavedAssignmentData(prev => ({
              ...prev,
              [cardKey]: {
                ...(prev[cardKey] || {}),
                rubricType: assignment.rubricType || 'standard',
                completionOnly: assignment.completionOnly || false,
                countsTowardsGrade: assignment.countsTowardsGrade !== false,
                title: assignment.title,
                aliases: assignment.aliases || [],
              }
            }));
          }
          // Update loaded assignment name to reflect current title
          setLoadedAssignmentName(assignment.title);
        } else if (saveResult.error) {
          console.error("Failed to save assignment:", saveResult.error);
          addToast("Failed to save assignment: " + saveResult.error, "error");
        }
      } catch (error) {
        console.error("Failed to auto-save assignment:", error);
      }
    }, 1500); // Debounce 1.5 seconds (slightly longer for assignment changes)

    return () => clearTimeout(saveTimeout);
  }, [assignment, importedDoc, settingsLoaded, loadedAssignmentName, isLoadingAssignment]);
}
