import { useState, useEffect } from "react";
import * as api from "../services/api";

/*
 * useSubscription — owns the billing subscription-status cluster pushed down from the
 * App.jsx shell (App.jsx decomposition). Loads subscription status when the Settings
 * "billing" sub-tab is selected. App calls this once and forwards the bundle to
 * SettingsTab -> SettingsBilling. Effect body + [settingsTab] dep preserved verbatim.
 */
export function useSubscription(settingsTab) {
  const [subscription, setSubscription] = useState(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);

  useEffect(() => {
    if (settingsTab !== "billing") return;
    setSubscriptionLoading(true);
    api.getSubscriptionStatus()
      .then((res) => { if (!res.error) setSubscription(res); })
      .catch(() => {})
      .finally(() => setSubscriptionLoading(false));
  }, [settingsTab]);

  return { subscription, setSubscription, subscriptionLoading, setSubscriptionLoading };
}
