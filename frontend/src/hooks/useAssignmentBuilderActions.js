import * as api from "../services/api";

/*
 * useAssignmentBuilderActions — the Builder assignment CRUD handlers (save config,
 * load, delete, export), pushed down from the App.jsx shell (App.jsx decomposition
 * slice 10). This is a FACTORY hook: it defines handler closures and returns them,
 * using NO internal React state/effects, so it imposes no hook-order constraint and is
 * simply called once during App's render. The handler bodies moved VERBATIM; the App
 * state values, setters, the skip-autosave ref, and the App-local textToRichHtml helper
 * they close over are passed in. `api` (an App-level import) is imported here.
 * NOTE: textToRichHtml is App-local (it is also used by the doc-import handler), so it
 * stays in App and is passed in rather than imported.
 */
export function useAssignmentBuilderActions({
  assignment,
  savedAssignments,
  loadedAssignmentName,
  docEditorModal,
  importedDoc,
  skipAutoSaveRef,
  textToRichHtml,
  addToast,
  setAssignment,
  setImportedDoc,
  setDocEditorModal,
  setLoadedAssignmentName,
  setSavedAssignments,
  setSavedAssignmentData,
  setIsLoadingAssignment,
}) {
  const saveAssignmentConfig = async () => {
    if (!assignment.title) {
      addToast("Please enter a title", "warning");
      return;
    }
    try {
      // Use editedHtml if available (preserves marker highlights)
      const docToSave = docEditorModal.editedHtml
        ? { ...importedDoc, html: docEditorModal.editedHtml }
        : importedDoc;
      const dataToSave = { ...assignment, importedDoc: docToSave };
      await api.saveAssignmentConfig(dataToSave);
      addToast("Assignment saved!", "success");
      setLoadedAssignmentName(assignment.title);
      const list = await api.listAssignments();
      if (list.assignments) setSavedAssignments(list.assignments);
      if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
    } catch (e) {
      addToast("Error saving: " + e.message, "error");
    }
  };

  const loadAssignment = async (name) => {
    try {
      setIsLoadingAssignment(true); // Prevent auto-save during load
      skipAutoSaveRef.current = true; // Don't auto-save data we just loaded
      const data = await api.loadAssignment(name);
      if (data.assignment) {
        // Set importedDoc FIRST to prevent race condition
        if (data.assignment.importedDoc) {
          let loadedHtml = data.assignment.importedDoc.html || "";
          // Re-generate HTML from text if current HTML has no real formatting (just <p> tags)
          const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(loadedHtml);
          if (!hasFormatting && data.assignment.importedDoc.text) {
            loadedHtml = textToRichHtml(data.assignment.importedDoc.text);
            data.assignment.importedDoc.html = loadedHtml;
          }
          // Clean orphaned exclude marker spans
          const loadedExcludes = data.assignment.excludeMarkers || [];
          if (loadedHtml.includes('data-marker-id="exclude-')) {
            if (loadedExcludes.length === 0) {
              // No exclude markers at all — strip all exclude spans
              while (loadedHtml.includes('data-marker-id="exclude-')) {
                loadedHtml = loadedHtml.replace(/<span[^>]*data-marker-id="exclude-[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
              }
            } else {
              // Has some exclude markers — strip any orphaned spans with index >= array length
              const excludeIdRegex = /data-marker-id="exclude-(\d+)(?:-[^"]*)?"/g;
              let idMatch;
              const foundIndices = new Set();
              while ((idMatch = excludeIdRegex.exec(loadedHtml)) !== null) {
                foundIndices.add(parseInt(idMatch[1]));
              }
              for (const idx of foundIndices) {
                if (idx >= loadedExcludes.length) {
                  const orphanRegex = new RegExp(`<span[^>]*data-marker-id="exclude-${idx}(?:-[^"]*)?\"[^>]*>(.*?)<\\/span>`, 'gis');
                  while (orphanRegex.test(loadedHtml)) {
                    orphanRegex.lastIndex = 0;
                    loadedHtml = loadedHtml.replace(orphanRegex, '$1');
                  }
                }
              }
            }
          }
          const cleanDoc = { ...data.assignment.importedDoc, html: loadedHtml };
          setImportedDoc(cleanDoc);
          // Also restore the highlighted HTML to the editor
          if (loadedHtml) {
            setDocEditorModal(prev => ({
              ...prev,
              editedHtml: loadedHtml
            }));
          }
        } else {
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
        }
        // Load markers and section point settings
        const useSectionPts = data.assignment.useSectionPoints || false;
        const effortPts = data.assignment.effortPoints ?? 15;
        let markers = data.assignment.customMarkers || [];

        // Only migrate markers if section points is enabled
        if (useSectionPts && markers.length > 0) {
          // Check if markers need migration (any string markers or markers without points)
          const needsMigration = markers.some(m =>
            typeof m === 'string' || (typeof m === 'object' && !m.points)
          );

          if (needsMigration) {
            // Distribute remaining points (100 - effort) evenly among markers
            const availablePoints = 100 - effortPts;
            const pointsPerMarker = Math.floor(availablePoints / markers.length);
            const remainder = availablePoints % markers.length;

            markers = markers.map((m, i) => {
              const markerText = typeof m === 'string' ? m : m.start;
              const markerType = typeof m === 'object' ? (m.type || 'written') : 'written';
              // Give first marker any remainder points
              const pts = pointsPerMarker + (i === 0 ? remainder : 0);
              return { start: markerText, points: pts, type: markerType };
            });
          }
        }

        setAssignment({
          title: data.assignment.title || "",
          subject: data.assignment.subject || "Social Studies",
          totalPoints: data.assignment.totalPoints || 100,
          instructions: data.assignment.instructions || "",
          questions: data.assignment.questions || [],
          customMarkers: markers,
          excludeMarkers: data.assignment.excludeMarkers || [],
          gradingNotes: data.assignment.gradingNotes || "",
          responseSections: data.assignment.responseSections || [],
          aliases: data.assignment.aliases || [],
          completionOnly: data.assignment.completionOnly || false,
          rubricType: data.assignment.rubricType || "standard",
          customRubric: data.assignment.customRubric || null,
          useSectionPoints: useSectionPts,
          sectionTemplate: data.assignment.sectionTemplate || "Custom",
          effortPoints: effortPts,
          dueDate: data.assignment.dueDate || "",
          latePenalty: {
            enabled: false,
            type: "points_per_day",
            amount: 10,
            tiers: [
              { daysLate: 1, penalty: 10 },
              { daysLate: 3, penalty: 25 },
              { daysLate: 7, penalty: 50 },
            ],
            maxPenalty: 50,
            gracePeriodHours: 0,
            ...(data.assignment.latePenalty || {}),
          },
        });
        setLoadedAssignmentName(name);
      }
      // Small delay before allowing auto-save again
      setTimeout(() => setIsLoadingAssignment(false), 500);
    } catch (e) {
      setIsLoadingAssignment(false);
      addToast("Error loading: " + e.message, "error");
    }
  };

  const deleteAssignment = async (name) => {
    if (!confirm(`Delete "${name}"?\n\nThis will permanently remove the assignment config, grading notes, answer key, and all grading setup. This cannot be undone.`)) return;
    try {
      await api.deleteAssignment(name);
      setSavedAssignments(savedAssignments.filter((a) => a !== name));
      addToast(`"${name}" deleted`, "success");
      if (loadedAssignmentName === name) {
        setAssignment({
          title: "",
          subject: "Social Studies",
          totalPoints: 100,
          instructions: "",
          questions: [],
          customMarkers: [],
          excludeMarkers: [],
          gradingNotes: "",
          responseSections: [],
          aliases: [],
          completionOnly: false,
          rubricType: "standard",
          customRubric: null,
          useSectionPoints: false,
          sectionTemplate: "Custom",
          effortPoints: 15,
          dueDate: "",
          latePenalty: {
            enabled: false,
            type: "points_per_day",
            amount: 10,
            tiers: [
              { daysLate: 1, penalty: 10 },
              { daysLate: 3, penalty: 25 },
              { daysLate: 7, penalty: 50 },
            ],
            maxPenalty: 50,
            gracePeriodHours: 0,
          },
        });
        setLoadedAssignmentName("");
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  const exportAssignment = async (format) => {
    try {
      // Convert customMarkers to questions format for backend
      const exportData = { ...assignment };
      if ((!exportData.questions || exportData.questions.length === 0) && exportData.customMarkers?.length > 0) {
        exportData.questions = exportData.customMarkers.map((m, i) => ({
          marker: (typeof m === 'string' ? m : m.start) || ('Section ' + (i + 1)),
          prompt: '',
          points: typeof m === 'object' ? (m.points || 10) : 10,
          type: typeof m === 'object' ? (m.type || 'written') : 'written',
        }));
      }
      const data = await api.exportAssignment({ assignment: exportData, format });
      if (data.error) addToast("Error: " + data.error, "error");
      else addToast("Assignment exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  return {
    saveAssignmentConfig,
    loadAssignment,
    deleteAssignment,
    exportAssignment,
  };
}
