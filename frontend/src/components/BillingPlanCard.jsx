import React from "react";
import * as api from "../services/api";

/**
 * BillingPlanCard — pure-prop subscription status card for SettingsBilling.
 * Extracted from SettingsBilling (CQ wave cq8-05 split).
 *
 * Renders loading state, active-plan card, or inactive-plan card with checkout
 * buttons. No local state, effects, or fetches — all values and handlers are props.
 */
export default function BillingPlanCard({ addToast, setSubscription, setSubscriptionLoading, subscription, subscriptionLoading }) {
  return (
    <>
      {subscriptionLoading ? (
        <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
          Loading subscription status...
        </div>
      ) : subscription && subscription.status === "active" ? (
        <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", marginBottom: "20px", border: "1px solid var(--glass-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <span style={{ background: "#10b981", color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "0.75rem", fontWeight: 600 }}>Active</span>
            <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>
              {subscription.plan === "month" ? "Monthly" : subscription.plan === "year" ? "Annual" : subscription.plan} Plan
            </span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
            {subscription.cancel_at_period_end
              ? "Cancels on: "
              : "Renews on: "}
            {new Date(subscription.current_period_end * 1000).toLocaleDateString()}
          </p>
          {subscription.cancel_at_period_end && (
            <p style={{ fontSize: "0.8rem", color: "#f59e0b", marginTop: "8px" }}>
              Your subscription will not renew. You can resubscribe anytime.
            </p>
          )}
          <button
            onClick={async () => {
              try {
                const res = await api.createPortalSession();
                if (res.portal_url) window.location.href = res.portal_url;
                else addToast(res.error || "Failed to open portal", "error");
              } catch { addToast("Failed to open billing portal", "error"); }
            }}
            style={{ marginTop: "16px", padding: "10px 20px", borderRadius: "8px", border: "none", background: "var(--accent-primary)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
          >
            Manage Subscription
          </button>
        </div>
      ) : (
        <div>
          <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", marginBottom: "20px", border: "1px solid var(--glass-border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
              <span style={{ background: "var(--text-secondary)", color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "0.75rem", fontWeight: 600 }}>No Active Plan</span>
            </div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Subscribe to unlock all Graider features.
            </p>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                onClick={async () => {
                  try {
                    const res = await api.createCheckoutSession("monthly");
                    if (res.checkout_url) window.location.href = res.checkout_url;
                    else addToast(res.error || "Failed to start checkout", "error");
                  } catch { addToast("Failed to start checkout", "error"); }
                }}
                style={{ padding: "10px 20px", borderRadius: "8px", border: "1px solid var(--accent-primary)", background: "transparent", color: "var(--accent-primary)", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
              >
                Subscribe Monthly
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await api.createCheckoutSession("annual");
                    if (res.checkout_url) window.location.href = res.checkout_url;
                    else addToast(res.error || "Failed to start checkout", "error");
                  } catch { addToast("Failed to start checkout", "error"); }
                }}
                style={{ padding: "10px 20px", borderRadius: "8px", border: "none", background: "var(--accent-primary)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
              >
                Subscribe Annual
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => {
          setSubscriptionLoading(true);
          api.getSubscriptionStatus()
            .then((res) => { if (!res.error) setSubscription(res); })
            .catch(() => {})
            .finally(() => setSubscriptionLoading(false));
        }}
        style={{ padding: "8px 16px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.8rem" }}
      >
        Refresh Status
      </button>
    </>
  );
}
