import * as api from "../../services/api";

// Handler bodies moved verbatim from BuilderTab.jsx (CQ wave-9 split; same
// factory pattern as student-portal/createPortalHandlers.js from wave 6 and
// district-setup/createConfigFormHandlers.js from wave 5). The shell owns all
// state and calls this factory on every render with the current props, so
// each handler closes over exactly the same per-render values it did when
// defined inline in the saved-assignments map (no memoization here, same as
// before the split — the inline handlers were recreated each render too).
// The per-item `name` closure variable became an explicit parameter.
export default function createSavedAssignmentHandlers(ctx) {
  const setIsLoadingAssignment = ctx.setIsLoadingAssignment;
  const skipAutoSaveRef = ctx.skipAutoSaveRef;
  const setImportedDoc = ctx.setImportedDoc;
  const setAssignment = ctx.setAssignment;
  const setLoadedAssignmentName = ctx.setLoadedAssignmentName;
  const setDocEditorModal = ctx.setDocEditorModal;
  const addToast = ctx.addToast;
  const textToRichHtml = ctx.textToRichHtml;
  const removeAllHighlightsFromHtml = ctx.removeAllHighlightsFromHtml;
  const applyAllHighlights = ctx.applyAllHighlights;
  const savedAssignmentData = ctx.savedAssignmentData;
  const setSavedAssignmentData = ctx.setSavedAssignmentData;

  // Was the saved-assignment card's onDoubleClick handler.
  const openSavedAssignment = async (name) => {
    setIsLoadingAssignment(true); // Prevent auto-save during load
    skipAutoSaveRef.current = true; // Don't auto-save data we just loaded
    const data = await api.loadAssignment(name);
    if (data.assignment) {
      // Set importedDoc FIRST to prevent race condition
      if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
        setImportedDoc(data.assignment.importedDoc);
      } else {
        setImportedDoc({ text: "", html: "", filename: "", loading: false });
      }

      // Load the assignment
      setAssignment({
        title: data.assignment.title || "",
        subject: data.assignment.subject || "Social Studies",
        totalPoints: data.assignment.totalPoints || 100,
        instructions: data.assignment.instructions || "",
        questions: data.assignment.questions || [],
        customMarkers: data.assignment.customMarkers || [],
        gradingNotes: data.assignment.gradingNotes || "",
        responseSections: data.assignment.responseSections || [],
        aliases: data.assignment.aliases || [],
      });
      setLoadedAssignmentName(name);
      setTimeout(() => setIsLoadingAssignment(false), 500);

      // If there's an imported doc, open the editor modal
      if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
        // Use HTML if available, otherwise convert plain text to simple HTML
        let docHtml = data.assignment.importedDoc.html || '';
        const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(docHtml);
        if (!hasFormatting && data.assignment.importedDoc.text) {
          docHtml = textToRichHtml(data.assignment.importedDoc.text);
        }
        // Re-apply highlights from loaded markers onto the HTML
        const loadedMarkers = data.assignment.customMarkers || [];
        const loadedExcludes = data.assignment.excludeMarkers || [];
        if (loadedMarkers.length > 0 || loadedExcludes.length > 0) {
          let cleanHtml = removeAllHighlightsFromHtml(docHtml);
          docHtml = applyAllHighlights(cleanHtml, loadedMarkers, loadedExcludes);
        }
        setDocEditorModal({
          show: true,
          editedHtml: docHtml,
          viewMode: 'formatted'
        });
        const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
        addToast(
          `Loaded "${name}" with ${markerCount} marker${markerCount !== 1 ? 's' : ''}`,
          'success'
        );
      } else {
        // No document - check if it has markers
        const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
        if (markerCount > 0) {
          addToast(`"${name}" has ${markerCount} marker${markerCount !== 1 ? 's' : ''} but no document. Re-import the document to view.`, 'warning');
        } else {
          addToast(`"${name}" has no document or markers. Import a document to get started.`, 'info');
        }
      }
    } else {
      setIsLoadingAssignment(false);
    }
  };

  // Was the star-toggle button's onClick handler.
  const toggleCountsTowardsGrade = async (name, e) => {
    e.stopPropagation();
    const currentValue = savedAssignmentData[name]?.countsTowardsGrade ?? true;
    const newValue = !currentValue;
    setSavedAssignmentData(prev => ({
      ...prev,
      [name]: { ...prev[name], countsTowardsGrade: newValue },
    }));
    try {
      const fullData = await api.loadAssignment(name);
      if (fullData.assignment) {
        await api.saveAssignmentConfig({
          ...fullData.assignment,
          countsTowardsGrade: newValue,
        });
      }
      addToast(
        newValue
          ? `"${name}" will count towards grade`
          : `"${name}" excluded from grade calculation`,
        "success"
      );
    } catch (err) {
      console.error("Error saving:", err);
    }
  };

  return { openSavedAssignment, toggleCountsTowardsGrade };
}
