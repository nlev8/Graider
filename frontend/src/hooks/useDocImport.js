import * as api from "../services/api";
import { removeAllHighlightsFromHtml, textToRichHtml } from "../utils/htmlHighlight";

/*
 * useDocImport — the Builder document import + doc-editor-open handlers, pushed down from
 * the App.jsx shell (App.jsx decomposition slice 16). FACTORY hook (no internal React
 * state/effects → no hook-order constraint). handleDocImport parses an uploaded file, and
 * (if the name matches a saved assignment) offers to load it; openDocEditor opens the
 * highlight editor. Bodies moved VERBATIM. The 9 App state values/setters they close over —
 * including the App-local applyAllHighlights helper — are passed in; api +
 * removeAllHighlightsFromHtml + textToRichHtml are imported here.
 *
 * IMPORTANT (slice-15 TDZ lesson): handleDocImport reads applyAllHighlights, a `const` arrow
 * declared later in App. So App must CALL useDocImport AFTER applyAllHighlights is defined,
 * or the render-time read of applyAllHighlights hits its temporal dead zone. The App.jsx
 * call site is positioned accordingly (verified by the App-mount smoke test).
 */
export function useDocImport({
  importedDoc,
  assignment,
  savedAssignments,
  applyAllHighlights,
  addToast,
  setImportedDoc,
  setAssignment,
  setLoadedAssignmentName,
  setDocEditorModal,
}) {
  const handleDocImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImportedDoc({ text: "", html: "", filename: file.name, loading: true });
    try {
      const data = await api.parseDocument(file);
      if (data.error) {
        addToast("Error parsing document: " + data.error, "error");
        setImportedDoc({ text: "", html: "", filename: "", loading: false });
      } else {
        // Use filename as title (cleaner than document metadata which is often generic)
        const newTitle = file.name
          .replace(/\.(docx|pdf|doc|txt)$/i, "")
          .replace(/_/g, " ")
          .replace(/\s+/g, " ")
          .trim();

        // Sanitize title the same way backend does for filename comparison
        const safeTitle = newTitle.replace(/[^a-zA-Z0-9 \-_]/g, "").trim();

        // Check if this assignment already exists (compare sanitized names)
        const existingName = savedAssignments.find(
          (name) => name.toLowerCase() === safeTitle.toLowerCase(),
        );

        if (existingName) {
          const confirmLoad = window.confirm(
            `An assignment named "${existingName}" already exists.\n\nClick OK to load existing settings with this document, or Cancel to skip.`,
          );
          if (confirmLoad) {
            // Load existing assignment config but use the NEW document text
            try {
              const existingData = await api.loadAssignment(existingName);
              if (existingData.assignment) {
                setAssignment({
                  title: existingData.assignment.title || "",
                  subject: existingData.assignment.subject || "Social Studies",
                  totalPoints: existingData.assignment.totalPoints || 100,
                  instructions: existingData.assignment.instructions || "",
                  questions: existingData.assignment.questions || [],
                  customMarkers: existingData.assignment.customMarkers || [],
                  excludeMarkers: existingData.assignment.excludeMarkers || [],
                  gradingNotes: existingData.assignment.gradingNotes || "",
                  responseSections:
                    existingData.assignment.responseSections || [],
                });
                setLoadedAssignmentName(existingName);
                // Use the freshly parsed document text, not the (possibly empty) saved one
                setImportedDoc({
                  text: data.text || "",
                  html: data.html || "",
                  filename: file.name,
                  loading: false,
                });
                // Open doc editor with highlights from existing markers
                let docHtml = data.html || "";
                const loadedMarkers = existingData.assignment.customMarkers || [];
                const loadedExcludes = existingData.assignment.excludeMarkers || [];
                if (loadedMarkers.length > 0 || loadedExcludes.length > 0) {
                  let cleanHtml = removeAllHighlightsFromHtml(docHtml);
                  docHtml = applyAllHighlights(cleanHtml, loadedMarkers, loadedExcludes);
                }
                setDocEditorModal({
                  show: true,
                  editedHtml: docHtml,
                  viewMode: "formatted",
                });
              }
            } catch (loadErr) {
              console.error("Failed to load existing assignment:", loadErr);
            }
            return;
          }
          // User chose not to load existing - cancel the import
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
          return;
        }

        setImportedDoc({
          text: data.text || "",
          html: data.html || "",
          filename: file.name,
          loading: false,
        });
        setLoadedAssignmentName("");
        setDocEditorModal({
          show: true,
          editedHtml: data.html || "",
          viewMode: "formatted",
        });
        if (!assignment.title) {
          setAssignment({ ...assignment, title: newTitle });
        }
      }
    } catch (err) {
      addToast("Error: " + err.message, "error");
      setImportedDoc({ text: "", html: "", filename: "", loading: false });
    }
  };

  const openDocEditor = () => {
    if (importedDoc.text || importedDoc.html) {
      let html = importedDoc.html;
      // Re-generate HTML from text if current HTML has no real formatting
      const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(html);
      if (!hasFormatting && importedDoc.text) {
        html = textToRichHtml(importedDoc.text);
        setImportedDoc({ ...importedDoc, html });
      }

      // If no markers but HTML has highlights, clean orphaned highlights
      const hasHighlights = html && html.includes('data-marker-id=');
      const hasMarkers = (assignment.customMarkers || []).length > 0;

      const hasExcludeMarkers = (assignment.excludeMarkers || []).length > 0;
      if (hasHighlights && !hasMarkers && !hasExcludeMarkers) {
        html = removeAllHighlightsFromHtml(html);
        // Also update importedDoc to persist the cleanup
        setImportedDoc({ ...importedDoc, html });
      }

      setDocEditorModal({
        show: true,
        editedHtml: html,
        viewMode: "formatted",
      });
    }
  };

  return {
    handleDocImport,
    openDocEditor,
  };
}
