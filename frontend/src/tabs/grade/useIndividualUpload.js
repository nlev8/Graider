import { useState, useEffect } from "react";
import { getAuthHeaders } from "../../services/api";

/*
 * useIndividualUpload — owns the individual-upload (paper/handwritten) state
 * + handlers, relocated verbatim from GradeTab.jsx (CQ wave-2 split; mirrors
 * the wave-1 useAnalyticsData precedent for state/effect clusters).
 *
 * Behavior-preserving notes:
 *   - The blob-URL revoke effect keeps its dependency array byte-identical
 *     ([individualUpload.preview]); since GradeTab is always-mounted, the
 *     hook's mount/unmount lifecycle is identical to the pre-split inline
 *     effect.
 *   - Handlers are intentionally NOT memoized (no useCallback) — same as the
 *     pre-split plain-const declarations recreated each render.
 */
export default function useIndividualUpload({
  config,
  globalAINotes,
  periods,
  selectedPeriod,
  periodStudents,
  gradeAssignment,
  addToast,
  setStatus,
}) {
  const [individualUpload, setIndividualUpload] = useState({
    file: null,
    studentName: "",
    studentInfo: null, // Full student info from CSV (id, email, etc.)
    preview: null,
    isGrading: false,
    result: null,
    showSuggestions: false,
  });

  // PR 3 — Codex Round 4 MINOR. Revoke blob URLs created by handleIndividualFileSelect
  // to prevent memory leaks. Pre-PR-3 the state lived in App and never unmounted, so the
  // only cleanup path was clearIndividualUpload(). With local state in an always-mounted
  // GradeTab, the cleanup runs whenever individualUpload.preview changes (the previous
  // value's URL gets revoked) and on component unmount.
  useEffect(() => {
    const url = individualUpload.preview;
    return () => {
      if (url && typeof url === "string" && url.startsWith("blob:")) {
        URL.revokeObjectURL(url);
      }
    };
  }, [individualUpload.preview]);

  // PR 3 — Handle individual file upload for paper/handwritten assignments.
  const handleIndividualFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const preview = file.type.startsWith("image/")
      ? URL.createObjectURL(file)
      : null;
    setIndividualUpload((prev) => ({
      ...prev,
      file,
      preview,
      result: null,
    }));
  };

  // PR 3 — Submit the individual upload to /api/grade-individual.
  const handleIndividualGrade = async () => {
    if (!individualUpload.file || !individualUpload.studentName.trim()) {
      addToast("Please select a file and enter the student name", "warning");
      return;
    }

    setIndividualUpload((prev) => ({ ...prev, isGrading: true, result: null }));

    try {
      const formData = new FormData();
      formData.append("file", individualUpload.file);
      formData.append("student_name", individualUpload.studentName.trim());
      formData.append("grade_level", config.grade_level);
      formData.append("subject", config.subject);
      formData.append("output_folder", config.output_folder);
      formData.append("globalAINotes", globalAINotes);
      formData.append("teacher_name", config.teacher_name || "");
      formData.append("school_name", config.school_name || "");
      // Pass class period for differentiated grading
      if (selectedPeriod) {
        const periodName = periods.find(p => p.filename === selectedPeriod)?.period_name || '';
        formData.append("classPeriod", periodName);
      }
      // Pass student info from CSV if available
      if (individualUpload.studentInfo) {
        formData.append(
          "studentInfo",
          JSON.stringify(individualUpload.studentInfo),
        );
      }
      // Pass assignment config if available
      if (
        gradeAssignment.gradingNotes ||
        gradeAssignment.customMarkers?.length > 0 ||
        gradeAssignment.title
      ) {
        formData.append("assignmentConfig", JSON.stringify(gradeAssignment));
      }

      const authHdrs = await getAuthHeaders();
      const response = await fetch("/api/grade-individual", {
        method: "POST",
        headers: { ...authHdrs },
        body: formData,
      });
      const result = await response.json();

      if (result.error) {
        addToast("Grading error: " + result.error, "error");
        setIndividualUpload((prev) => ({ ...prev, isGrading: false }));
        return;
      }

      setIndividualUpload((prev) => ({ ...prev, isGrading: false, result }));

      // Add to results list
      setStatus((prev) => ({
        ...prev,
        results: [...prev.results, result],
      }));

      addToast(
        `Graded - ${individualUpload.studentName}: ${result.letter_grade} (${result.score}%)`,
        "success",
      );
    } catch (error) {
      console.error("Individual grading error:", error);
      addToast("Failed to grade: " + error.message, "error");
      setIndividualUpload((prev) => ({ ...prev, isGrading: false }));
    }
  };

  // PR 3 — Clear the individual upload form. Note: the blob-URL revoke effect
  // also runs when preview changes, but explicit cleanup here covers the case
  // where the user clicks the X button without replacing the file.
  const clearIndividualUpload = () => {
    if (individualUpload.preview) {
      URL.revokeObjectURL(individualUpload.preview);
    }
    setIndividualUpload({
      file: null,
      studentName: "",
      studentInfo: null,
      preview: null,
      isGrading: false,
      result: null,
      showSuggestions: false,
    });
  };

  // PR 3 — Filter students for the individual-upload autocomplete.
  const getStudentSuggestions = (input) => {
    if (!input || input.length < 2) return [];
    const lowerInput = input.toLowerCase();
    return periodStudents
      .filter((s) => {
        const fullName = s.full?.toLowerCase() || "";
        const first = s.first?.toLowerCase() || "";
        const last = s.last?.toLowerCase() || "";
        return (
          fullName.includes(lowerInput) ||
          first.includes(lowerInput) ||
          last.includes(lowerInput)
        );
      })
      .slice(0, 5); // Limit to 5 suggestions
  };

  return {
    individualUpload,
    setIndividualUpload,
    handleIndividualFileSelect,
    handleIndividualGrade,
    clearIndividualUpload,
    getStudentSuggestions,
  };
}
