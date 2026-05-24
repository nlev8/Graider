import { useEffect } from "react";
import * as api from "../services/api";

/*
 * useSettingsAutoSave — the debounced auto-save side-effects for Settings-domain data,
 * pushed down from the App.jsx shell (App.jsx decomposition). Pure side-effect hook
 * (owns no state, returns nothing): when config/globalAINotes or rubric change after the
 * initial load, it debounce-saves them to the backend. Effect bodies + dep arrays moved
 * verbatim. App calls this once with the relevant state as inputs.
 */
export function useSettingsAutoSave({ config, globalAINotes, rubric, settingsLoaded }) {
  // Auto-save settings when they change (debounced)
  useEffect(() => {
    if (!settingsLoaded) return; // Don't save until initial load is complete

    const saveTimeout = setTimeout(() => {
      api.saveGlobalSettings({ globalAINotes, config }).catch(console.error);
    }, 1000); // Debounce 1 second

    return () => clearTimeout(saveTimeout);
  }, [config, globalAINotes, settingsLoaded]);

  // Auto-save rubric when it changes (debounced)
  useEffect(() => {
    if (!settingsLoaded) return;

    const saveTimeout = setTimeout(() => {
      api.saveRubric(rubric).catch(console.error);
    }, 1000);

    return () => clearTimeout(saveTimeout);
  }, [rubric, settingsLoaded]);
}
