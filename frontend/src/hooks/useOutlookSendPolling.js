import { useState, useEffect } from "react";
import * as api from "../services/api";

/*
 * useOutlookSendPolling — owns the Outlook email-send polling cluster pushed down from
 * the App.jsx shell (App.jsx decomposition). Polls the Outlook send-status endpoint while
 * outlookSendPolling is set, toasting on completion and marking the associated portal
 * confirmations sent. App calls this once with its portal-confirmation refs/handlers
 * (which remain App-owned) and forwards the bundle to the consuming tab. Effect body +
 * [outlookSendPolling] dep array moved verbatim.
 */
export function useOutlookSendPolling({
  addToast,
  pendingConfirmationIds,
  pendingConfirmationFilenames,
  setPendingConfirmations,
  fetchPendingConfirmations,
}) {
  const [outlookSendStatus, setOutlookSendStatus] = useState({ status: "idle", sent: 0, total: 0, failed: 0, message: "" });
  const [outlookSendPolling, setOutlookSendPolling] = useState(false);

  useEffect(() => {
    if (!outlookSendPolling) return;
    var interval = setInterval(async function() {
      try {
        var data = await api.getOutlookSendStatus();
        setOutlookSendStatus(data);
        if (data.status === "done" || data.status === "error" || data.status === "idle") {
          setOutlookSendPolling(false);
          if (data.status === "done") {
            addToast("Outlook: Sent " + data.sent + " of " + data.total + " emails" + (data.failed > 0 ? " (" + data.failed + " failed)" : ""), data.failed > 0 ? "warning" : "success");
          }
          // Mark portal confirmation emails as sent if any were being processed
          if (pendingConfirmationIds.current.length > 0) {
            var ids = pendingConfirmationIds.current;
            pendingConfirmationIds.current = [];
            api.markConfirmationsSent(ids, data.status === "done" ? "sent" : "failed").catch(function() {});
            setPendingConfirmations(0);
          }
          // Mark file-based confirmations as sent and refresh count
          if (pendingConfirmationFilenames.current.length > 0) {
            var fnames = pendingConfirmationFilenames.current;
            pendingConfirmationFilenames.current = [];
            api.markFileConfirmationsSent(fnames).then(function() {
              fetchPendingConfirmations();
            }).catch(function() {});
          }
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 2000);
    return function() { clearInterval(interval); };
  }, [outlookSendPolling]);

  return { outlookSendStatus, setOutlookSendStatus, outlookSendPolling, setOutlookSendPolling };
}
