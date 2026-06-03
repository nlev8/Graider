import { useEffect } from "react";
import * as api from "../services/api";

/*
 * useGradingStatusPoll — the adaptive status-polling loop that runs while a grading
 * job is in progress, pushed down from the App.jsx shell (App.jsx decomposition slice 6).
 * Pure side-effect hook (owns no state, returns nothing). `status` stays owned by App
 * (it is read in ~57 places across the render); this hook receives `status` + `setStatus`
 * and runs the poll. The effect body + dep array [status.is_running] moved VERBATIM,
 * including the exponential-backoff cadence, the visibility-driven snap-back, and the
 * generation guard against duplicate parallel polling chains.
 */
export function useGradingStatusPoll({ status, setStatus }) {
  // Poll status while grading. Closes audit MINOR (Codex full-codebase
  // audit 2026-05-06): the previous fixed-500ms interval amplified
  // multi-tab load (~2 req/sec/tab × N tabs) and server cost grew
  // linearly with idle teachers staring at the grading screen. Now
  // the cadence backs off exponentially (500ms → 1s → 2s → 4s → 8s)
  // while grading is steady, and snaps back to 500ms whenever the
  // server reports activity (log line, result, or progress tick) so
  // the UI stays responsive when work IS happening. Tab visibility
  // throttling further reduces traffic when the tab is hidden.
  useEffect(() => {
    if (!status.is_running) return;
    let cancelled = false;
    let timeoutId = null;
    let generation = 0;          // monotonic; bumped by visibilitychange to invalidate stale ticks
    let currentDelay = 500;
    const MIN_DELAY = 500;
    const MAX_DELAY = 8000;
    const HIDDEN_DELAY = 15000;
    let lastLogLen = (status.log && status.log.length) || 0;
    let lastResultsLen = (status.results && status.results.length) || 0;
    let lastProgress = status.progress || 0;

    const tick = async (myGen) => {
      if (cancelled) return;
      // Round-2 Codex LOW fold: if a visibility event bumped the
      // generation while this tick was queued OR awaiting, this stale
      // chain MUST NOT schedule its own next tick. The fresh chain
      // started by the visibility handler owns scheduling now.
      if (myGen !== generation) return;
      try {
        const data = await api.getStatus();
        if (cancelled || myGen !== generation) return;
        setStatus(data);
        const newLogLen = (data.log && data.log.length) || 0;
        const newResultsLen = (data.results && data.results.length) || 0;
        const newProgress = data.progress || 0;
        const sawActivity = (
          newLogLen > lastLogLen ||
          newResultsLen > lastResultsLen ||
          newProgress > lastProgress
        );
        lastLogLen = newLogLen;
        lastResultsLen = newResultsLen;
        lastProgress = newProgress;
        if (!data.is_running) {
          // Grading finished — let the effect cleanup re-trigger via
          // the `is_running` dep change.
          return;
        }
        // Activity → snap to MIN_DELAY. Idle → exponential backoff.
        if (sawActivity) {
          currentDelay = MIN_DELAY;
        } else {
          currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
        }
      } catch (error) {
        // Round-3 Codex LOW fold: stale rejected polls (myGen !==
        // generation) must NOT mutate the shared currentDelay or they
        // would partially undo the visibility-driven snap-back from
        // the new chain.
        if (cancelled || myGen !== generation) return;
        console.error("Status poll error:", error);
        // Network errors → also back off so we don't hammer a flaky API.
        currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
      }
      if (cancelled || myGen !== generation) return;
      const nextDelay = (typeof document !== 'undefined' && document.hidden)
        ? Math.max(currentDelay, HIDDEN_DELAY)
        : currentDelay;
      timeoutId = setTimeout(() => tick(myGen), nextDelay);
    };

    // Round-1 Codex LOW fold (revised in round-2): when the tab becomes
    // visible again, pull the next tick forward so the user doesn't
    // see stale status for up to 15s. We bump `generation` so any
    // in-flight or queued tick from the prior chain self-cancels its
    // re-scheduling — preventing duplicate parallel polling chains.
    const onVisibilityChange = () => {
      if (cancelled) return;
      if (typeof document !== 'undefined' && !document.hidden) {
        currentDelay = MIN_DELAY;
        if (timeoutId) clearTimeout(timeoutId);
        // If a tick is in-flight, it'll see myGen !== generation and
        // bail out of re-scheduling. We schedule the new chain now;
        // even if both fire `getStatus` once, the stale chain stops
        // after its current tick instead of forking a parallel loop.
        generation += 1;
        const myGen = generation;
        timeoutId = setTimeout(() => tick(myGen), 0);
      }
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange);
    }

    const initialGen = generation;
    timeoutId = setTimeout(() => tick(initialGen), currentDelay);
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibilityChange);
      }
    };
  }, [status.is_running]);
}
