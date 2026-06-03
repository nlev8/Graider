import { useEffect } from "react";

/*
 * useBillingRedirect — handles the Stripe billing redirect URL params on mount
 * (?billing=success | cancel | portal-return): toasts the outcome, opens the
 * Settings > Billing tab, and cleans the URL. Pushed down from the App.jsx shell
 * (App.jsx decomposition slice 4). The effect body moved VERBATIM; the three
 * functions it calls (addToast, setActiveTab, setSettingsTab) are passed in.
 *
 * NOTE: the Clever/ClassLink login-redirect params are handled in useAuthSession
 * (slice 3), not here — slice 4 is billing-only.
 */
export function useBillingRedirect({ addToast, setActiveTab, setSettingsTab }) {
  // Handle Stripe redirect URL params (?billing=success or ?billing=cancel)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const billingParam = params.get("billing");
    if (billingParam === "success") {
      addToast("Subscription activated successfully!", "success");
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (billingParam === "cancel") {
      addToast("Checkout cancelled", "info");
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (billingParam === "portal-return") {
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);
}
