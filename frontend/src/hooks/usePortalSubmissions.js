import { useState, useEffect } from "react";
import * as api from "../services/api";

/*
 * usePortalSubmissions — owns the portal-submissions cluster pushed down from the App.jsx
 * shell (App.jsx decomposition). Polls portal submissions for the Results tab every 30s
 * while an approved teacher session is active, and refreshes the shared pending-confirmations
 * count (setPendingConfirmations stays App-owned and is passed in). App calls this once and
 * forwards portalSubmissions to the Results tab. Effect body + [user, showTutorial,
 * userApproved] dep array moved verbatim.
 */
export function usePortalSubmissions({ user, showTutorial, userApproved, setPendingConfirmations }) {
  const [portalSubmissions, setPortalSubmissions] = useState([]);

  // Fetch portal submissions for Results tab
  useEffect(() => {
    if (!user || showTutorial || userApproved !== true) return;
    const loadPortalSubmissions = async () => {
      try {
        const data = await api.getPortalSubmissions();
        if (data.submissions) setPortalSubmissions(data.submissions);
        if (data.pending_confirmations != null) setPendingConfirmations(data.pending_confirmations);
      } catch (e) {
        // Silently fail - portal submissions are supplementary
      }
    };
    loadPortalSubmissions();
    const interval = setInterval(loadPortalSubmissions, 30000);
    return () => clearInterval(interval);
  }, [user, showTutorial, userApproved]);

  return { portalSubmissions };
}
