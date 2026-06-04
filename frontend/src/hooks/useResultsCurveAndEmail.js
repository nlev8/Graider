import * as api from "../services/api";

/*
 * useResultsCurveAndEmail — the Results-tab grade-curve + email/approval handlers, pushed
 * down from the App.jsx shell (App.jsx decomposition slice 12). FACTORY hook (no internal
 * React state/effects → no hook-order constraint), called once during App's render. The
 * handler bodies moved VERBATIM. The small getLetterGrade helper is used ONLY by applyCurve,
 * so it moved in as a factory-internal helper (not returned). getDefaultEmailBody is
 * App-local (also used by the render), so it is passed in. The ~18 state values/setters the
 * handlers close over are passed in; api is imported here (also stays imported in App).
 */
export function useResultsCurveAndEmail({
  addToast,
  status,
  resultsPeriodFilter,
  editedResults,
  editedEmails,
  curveModal,
  emailPreview,
  config,
  getDefaultEmailBody,
  setEditedResults,
  setEditedEmails,
  setStatus,
  setCurveModal,
  setEmailPreview,
  setEmailStatus,
  setEmailApprovals,
  setOutlookSendPolling,
  setOutlookSendStatus,
}) {
  const getLetterGrade = (score) => {
    const s = parseInt(score) || 0;
    return s >= 90 ? "A" : s >= 80 ? "B" : s >= 70 ? "C" : s >= 60 ? "D" : "F";
  };

  // Apply curve to filtered results
  const applyCurve = () => {
    const { curveType, curveValue } = curveModal;
    const val = parseFloat(curveValue) || 0;
    if (val === 0) {
      addToast("Please enter a curve value", "warning");
      return;
    }

    // Get indices of filtered results (based on period filter)
    const filteredIndices = [];
    status.results.forEach((r, idx) => {
      if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
      filteredIndices.push(idx);
    });

    if (filteredIndices.length === 0) {
      addToast("No results to curve", "warning");
      return;
    }

    // Apply curve to each result
    const newEditedResults = editedResults.length > 0 ? [...editedResults] : [...status.results];
    const newEditedEmails = { ...editedEmails };
    let curvedCount = 0;

    filteredIndices.forEach((idx) => {
      const result = status.results[idx];
      const oldScore = parseInt(result.score) || 0;
      const oldGrade = result.letter_grade || getLetterGrade(oldScore);

      // Calculate new score based on curve type
      let newScore;
      if (curveType === "add") {
        newScore = Math.min(100, Math.max(0, oldScore + val));
      } else if (curveType === "percent") {
        newScore = Math.min(100, Math.max(0, Math.round(oldScore * (1 + val / 100))));
      } else if (curveType === "set_min") {
        newScore = Math.max(val, oldScore);
      }

      const newGrade = getLetterGrade(newScore);

      // Skip if no change
      if (newScore === oldScore) return;

      curvedCount++;

      // Update the result
      if (!newEditedResults[idx]) newEditedResults[idx] = { ...result };
      newEditedResults[idx] = {
        ...newEditedResults[idx],
        score: newScore,
        letter_grade: newGrade,
        edited: true,
      };

      // Update feedback if it contains the old score/grade
      let feedback = newEditedResults[idx].feedback || "";
      if (feedback) {
        // Replace score patterns like "85/100" or "Score: 85"
        feedback = feedback.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");
        feedback = feedback.replace(new RegExp("Score:\\s*" + oldScore, "gi"), "Score: " + newScore);
        feedback = feedback.replace(new RegExp("\\b" + oldScore + "%", "g"), newScore + "%");
        // Replace letter grade if mentioned
        if (oldGrade !== newGrade) {
          feedback = feedback.replace(new RegExp("\\(" + oldGrade + "\\)", "g"), "(" + newGrade + ")");
          feedback = feedback.replace(new RegExp("Grade:\\s*" + oldGrade + "\\b", "gi"), "Grade: " + newGrade);
        }
        newEditedResults[idx].feedback = feedback;
      }

      // Update email if it exists
      if (newEditedEmails[idx]) {
        let subject = newEditedEmails[idx].subject || "";
        let body = newEditedEmails[idx].body || "";

        // Update subject
        subject = subject.replace(new RegExp(": " + oldGrade + "$"), ": " + newGrade);

        // Update body
        body = body.replace(new RegExp("GRADE: " + oldScore + "/100 \\(" + oldGrade + "\\)"), "GRADE: " + newScore + "/100 (" + newGrade + ")");
        body = body.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");

        newEditedEmails[idx] = { ...newEditedEmails[idx], subject, body };
      }
    });

    // Sync to state
    setEditedResults(newEditedResults);
    setEditedEmails(newEditedEmails);

    // Also update status.results
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      filteredIndices.forEach((idx) => {
        if (newEditedResults[idx]) {
          updatedResults[idx] = { ...newEditedResults[idx] };
        }
      });
      return { ...prev, results: updatedResults };
    });

    setCurveModal({ ...curveModal, show: false });
    addToast(`Applied ${curveType === "add" ? "+" + val + " points" : curveType === "percent" ? "+" + val + "%" : "min " + val} curve to ${curvedCount} result${curvedCount !== 1 ? "s" : ""}`, "success");
  };

  const sendEmails = async () => {
    setEmailPreview({ ...emailPreview, show: false });
    const results = editedResults.length > 0 ? editedResults : status.results;
    if (results.length === 0) return;
    setEmailStatus({
      sending: true,
      sent: 0,
      failed: 0,
      message: "Sending emails...",
    });
    try {
      const data = await api.sendEmails(results, config.teacher_email, config.teacher_name, config.email_signature);
      setEmailStatus({
        sending: false,
        sent: data.sent || 0,
        failed: data.failed || 0,
        message: data.error
          ? `Error: ${data.error}`
          : `Sent ${data.sent} emails${data.failed > 0 ? `, ${data.failed} failed` : ""}`,
      });
    } catch (e) {
      setEmailStatus({
        sending: false,
        sent: 0,
        failed: 0,
        message: `Error: ${e.message}`,
      });
    }
  };

  // Send email for a single student
  const sendSingleEmail = async (result, index) => {
    const edited = editedEmails[index];
    const emailToUse = edited?.email || result.student_email;
    if (!emailToUse) {
      addToast("No email address for " + result.student_name, "error");
      return;
    }
    try {
      const emailResult = {
        ...result,
        student_email: emailToUse,
        custom_email_subject: edited?.subject || `Grade Report: ${result.assignment}`,
        custom_email_body: edited?.body || getDefaultEmailBody(index),
      };
      const response = await api.sendOutlookEmails({
        results: [emailResult],
        type: "student",
        teacher_name: config.teacher_name,
        email_signature: config.email_signature,
      });
      if (response.error) {
        addToast(response.error, "error");
      } else {
        setOutlookSendPolling(true);
        setOutlookSendStatus({ status: "running", sent: 0, total: response.total || 1, failed: 0, message: "Sending..." });
        addToast("Sending via Outlook to " + result.student_name, "info");
      }
    } catch (e) {
      addToast("Error sending email: " + e.message, "error");
    }
  };

  // Update approval status with persistence
  const updateApprovalStatus = async (index, approval) => {
    setEmailApprovals((prev) => ({ ...prev, [index]: approval }));
    // Also update the result object so the useEffect that rebuilds approvals
    // from status.results will preserve this approval
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      if (updatedResults[index]) {
        updatedResults[index] = { ...updatedResults[index], email_approval: approval };
      }
      return { ...prev, results: updatedResults };
    });
    // Persist to backend
    const result = status.results[index];
    if (result?.filename) {
      try {
        await api.updateApproval(result.filename, approval);
      } catch (e) {
        console.error("Error saving approval:", e);
      }
    }
  };

  // Bulk update approvals with persistence
  const updateApprovalsBulk = async (approvals) => {
    setEmailApprovals(approvals);
    // Build filename -> approval map for API
    const filenameApprovals = {};
    Object.entries(approvals).forEach(([idx, approval]) => {
      const result = status.results[parseInt(idx)];
      if (result?.filename) {
        filenameApprovals[result.filename] = approval;
      }
    });
    if (Object.keys(filenameApprovals).length > 0) {
      try {
        await api.updateApprovalsBulk(filenameApprovals);
      } catch (e) {
        console.error("Error saving approvals:", e);
      }
    }
  };

  return {
    applyCurve,
    sendEmails,
    sendSingleEmail,
    updateApprovalStatus,
    updateApprovalsBulk,
  };
}
