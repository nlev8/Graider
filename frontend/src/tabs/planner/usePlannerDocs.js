import { useState, useEffect } from "react";
import * as api from "../../services/api";

/*
 * usePlannerDocs — owns the reference-document clusters (standards matching,
 * preview reset, doc upload), relocated verbatim from PlannerTab.jsx
 * (CQ wave-3 split).
 *
 * History (App.jsx → PlannerTab moves during the Planner extraction sprint):
 *   - Matching cluster (PR 8a): matchingInProgress + matchResults +
 *     handleMatchStandards + removeUploadedDoc. removeUploadedDoc moves with
 *     the cluster because it calls setMatchResults(null) on doc removal.
 *   - Preview cluster (PR 8c): previewResults + its reset effect (fires on
 *     lessonPlan or generatedAssignment ref change, clearing stale preview
 *     results).
 *   - Doc upload cluster (PR 8b): docUploading + handleDocUpload.
 *
 * uploadedDocs + setUploadedDocs + selectedStandards + config + addToast +
 * lessonPlan + generatedAssignment remain App-shell props, received here as
 * hook args.
 *
 * Behavior-preserving notes: the preview-reset effect keeps its dependency
 * array byte-identical ([lessonPlan, generatedAssignment]); the hook is
 * called unconditionally from the PlannerTab shell, before useLessonGeneration,
 * preserving the pre-split effect declaration order. Handlers are
 * intentionally NOT memoized.
 */
export default function usePlannerDocs({
  uploadedDocs,
  setUploadedDocs,
  config,
  addToast,
  selectedStandards,
  lessonPlan,
  generatedAssignment,
}) {
  const [matchingInProgress, setMatchingInProgress] = useState(false);
  const [matchResults, setMatchResults] = useState(null);

  const handleMatchStandards = async () => {
    if (uploadedDocs.length === 0 || !config.subject || !config.grade_level) {
      addToast("Upload documents and set subject/grade first", "warning");
      return;
    }
    setMatchingInProgress(true);
    try {
      const combinedText = uploadedDocs.map(d => d.text).join("\n\n");
      const result = await api.alignDocumentToStandards({ documentText: combinedText, subject: config.subject, grade: config.grade_level });
      setMatchResults(result);
      if (result && result.matched_standards) {
        const matchedCodes = (result.matched_standards || []).filter(a => a.confidence >= 0.4).map(a => a.code);
        // Alert if currently selected standards conflict with document content
        if (selectedStandards.length > 0 && matchedCodes.length > 0) {
          const conflicts = selectedStandards.filter(code => !matchedCodes.includes(code));
          if (conflicts.length > 0) {
            addToast("Heads up: " + conflicts.length + " selected standard" + (conflicts.length > 1 ? "s" : "") + " (" + conflicts.join(", ") + ") may not align with your uploaded documents", "warning", 8000);
          }
        }
        if (matchedCodes.length > 0) {
          addToast(matchedCodes.length + " matching standards found — click to select", "info");
        } else {
          addToast("No strong standard matches found in uploaded documents", "warning");
        }
      }
    } catch (err) {
      addToast("Matching error: " + err.message, "error");
    } finally {
      setMatchingInProgress(false);
    }
  };

  const removeUploadedDoc = (index) => {
    setUploadedDocs(prev => prev.filter((_, i) => i !== index));
    setMatchResults(null);
  };

  const [previewResults, setPreviewResults] = useState(null);

  useEffect(() => {
    setPreviewResults(null);
  }, [lessonPlan, generatedAssignment]);

  const [docUploading, setDocUploading] = useState(false);

  const handleDocUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setDocUploading(true);
    try {
      for (const file of files) {
        const textResult = await api.extractTextFromFile(file);
        if (textResult && textResult.text) {
          setUploadedDocs(prev => [...prev, {
            filename: file.name,
            size: file.size,
            text: textResult.text,
          }]);
        } else {
          addToast("Could not extract text from " + file.name, "warning");
        }
      }
    } catch (err) {
      addToast("Upload error: " + err.message, "error");
    } finally {
      setDocUploading(false);
      e.target.value = "";
    }
  };

  return {
    matchingInProgress,
    matchResults,
    handleMatchStandards,
    removeUploadedDoc,
    previewResults, setPreviewResults,
    docUploading,
    handleDocUpload,
  };
}
