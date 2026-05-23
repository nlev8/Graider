import { useState, useEffect } from "react";
import * as api from "../services/api";

/*
 * useFocusPolling — owns the Focus (SIS) send/upload polling clusters pushed down from
 * the App.jsx shell (App.jsx decomposition). Polls the comms-send and comments-upload
 * status endpoints while their respective polling flag is set, toasting on completion.
 * App calls this once (with addToast) and forwards the bundle to the consuming tab.
 * Effect bodies + dep arrays moved verbatim.
 */
export function useFocusPolling(addToast) {
  const [focusCommsStatus, setFocusCommsStatus] = useState({ status: "idle", sent: 0, total: 0, failed: 0, skipped: 0, message: "" });
  const [focusCommsPolling, setFocusCommsPolling] = useState(false);
  const [focusCommentsStatus, setFocusCommentsStatus] = useState({ status: "idle", entered: 0, total: 0, failed: 0, message: "" });
  const [focusCommentsPolling, setFocusCommentsPolling] = useState(false);

  // Focus comms polling
  useEffect(() => {
    if (!focusCommsPolling) return;
    var interval = setInterval(async function() {
      try {
        var data = await api.getFocusCommsStatus();
        setFocusCommsStatus(data);
        if (data.status === "done" || data.status === "error" || data.status === "idle") {
          setFocusCommsPolling(false);
          if (data.status === "done") {
            addToast("Focus: Sent " + data.sent + " of " + data.total + " messages" + (data.failed > 0 ? " (" + data.failed + " failed)" : ""), data.failed > 0 ? "warning" : "success");
          }
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 2000);
    return function() { clearInterval(interval); };
  }, [focusCommsPolling]);

  // Focus comments upload polling
  useEffect(() => {
    if (!focusCommentsPolling) return;
    var interval = setInterval(async function() {
      try {
        var data = await api.getFocusCommentsStatus();
        setFocusCommentsStatus(data);
        if (data.status === "done" || data.status === "error" || data.status === "idle") {
          setFocusCommentsPolling(false);
          if (data.status === "done") {
            addToast("Focus: Entered " + data.entered + " comments" + (data.failed > 0 ? " (" + data.failed + " failed)" : "") + (data.skipped > 0 ? " (" + data.skipped + " skipped)" : ""), data.failed > 0 ? "warning" : "success");
          }
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 2000);
    return function() { clearInterval(interval); };
  }, [focusCommentsPolling]);

  return {
    focusCommsStatus, setFocusCommsStatus, focusCommsPolling, setFocusCommsPolling,
    focusCommentsStatus, setFocusCommentsStatus, focusCommentsPolling, setFocusCommentsPolling,
  };
}
