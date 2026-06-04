import { getMarkerText } from "../utils/markerHelpers";
import { highlightTextInHtml, removeAllHighlightsFromHtml } from "../utils/htmlHighlight";

/*
 * useMarkerEditing — the doc-editor marker handlers (add a selected-text marker;
 * remove a marker and re-apply remaining highlights), pushed down from the App.jsx shell
 * (App.jsx decomposition slice 15). FACTORY hook (no internal React state/effects → no
 * hook-order constraint), called once during render. Two source ranges joined (the dead
 * setEndMarker and the unrelated handleGenerateModelAnswers between them stayed in App).
 * Bodies moved VERBATIM; the 11 App state values/setters/refs + the App-local
 * HIGHLIGHT_COLORS constant + applyAllHighlights helper they close over are passed in.
 * The pure utils getMarkerText / highlightTextInHtml / removeAllHighlightsFromHtml are
 * imported directly.
 */
export function useMarkerEditing({
  docHtmlRef,
  highlighterMode,
  assignment,
  docEditorModal,
  importedDoc,
  HIGHLIGHT_COLORS,
  applyAllHighlights,
  addToast,
  setAssignment,
  setDocEditorModal,
  setImportedDoc,
}) {
  const addSelectedAsMarker = () => {
    let text = "";
    try {
      if (docHtmlRef.current?.contentDocument) {
        const sel = docHtmlRef.current.contentDocument.getSelection();
        if (sel) text = sel.toString().trim();
      }
    } catch (e) {}
    if (!text) {
      const sel = window.getSelection();
      text = sel ? sel.toString().trim() : "";
    }
    if (text && text.length > 2 && text.length < 2000) {
      if (highlighterMode === "start") {
        // Adding a new start marker
        const exists = (assignment.customMarkers || []).some(m =>
          typeof m === 'string' ? m === text : m.start === text
        );
        if (!exists) {
          const newMarkers = [...(assignment.customMarkers || []), text];
          const markerIndex = newMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.start,
            `start-${markerIndex}`
          );

          setAssignment({ ...assignment, customMarkers: newMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Start marker added (green)", "success");
        }
      } else if (highlighterMode === "exclude") {
        // Adding an exclude marker - section to NOT grade
        const exists = (assignment.excludeMarkers || []).some(m => m === text);
        if (!exists) {
          const newExcludeMarkers = [...(assignment.excludeMarkers || []), text];
          const excludeIndex = newExcludeMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.exclude,
            `exclude-${excludeIndex}`
          );

          setAssignment({ ...assignment, excludeMarkers: newExcludeMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Exclude marker added (orange) - this section will NOT be graded", "success");
        } else {
          addToast("This section is already marked as excluded", "warning");
        }
      } else {
        // Adding an end marker - attach to the last marker that doesn't have one
        const markers = [...(assignment.customMarkers || [])];
        const lastWithoutEnd = markers.findIndex((m, i) => {
          // Find first marker without an end marker
          return typeof m === 'string' || !m.end;
        });

        if (lastWithoutEnd >= 0) {
          const startText = getMarkerText(markers[lastWithoutEnd]);
          markers[lastWithoutEnd] = { start: startText, end: text };

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.end,
            `end-${lastWithoutEnd}`
          );

          setAssignment({ ...assignment, customMarkers: markers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("End marker added (red)", "success");
        } else {
          addToast("Add a start marker first", "warning");
        }
      }
    } else if (text.length <= 2) {
      addToast("Please select more text (at least 3 characters)", "warning");
    } else if (text.length >= 2000) {
      addToast(
        "Selection too long. Please select less text (under 2000 characters)",
        "warning",
      );
    }
  };

  const removeMarker = (marker, markerIndex) => {
    const markerText = getMarkerText(marker);

    // Remove ALL highlights and re-apply remaining ones (avoids index mismatch issues)
    let cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);

    // Filter out the removed marker
    const remainingMarkers = (assignment.customMarkers || []).filter(
      (m) => getMarkerText(m) !== markerText,
    );

    // Re-apply highlights for remaining markers AND exclude markers
    const newHtml = applyAllHighlights(cleanHtml, remainingMarkers, assignment.excludeMarkers);

    setAssignment({
      ...assignment,
      customMarkers: remainingMarkers,
    });

    // Update BOTH docEditorModal AND importedDoc
    setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
    setImportedDoc({ ...importedDoc, html: newHtml });
  };

  return {
    addSelectedAsMarker,
    removeMarker,
  };
}
