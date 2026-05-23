import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function SettingsBilling({ addToast, config, costSummary, setConfig, setCostSummary, setSubscription, setSubscriptionLoading, subscription, subscriptionLoading }) {
  return (
              <>
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="CreditCard" size={20} style={{ color: "#6366f1" }} />
                    Subscription & Billing
                  </h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
                    Manage your Graider subscription plan and billing details.
                  </p>

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
                </div>

                {/* API Cost Controls */}
                <div style={{ marginTop: "30px" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="Shield" size={20} style={{ color: "#f59e0b" }} />
                    API Cost Controls
                  </h3>
                  <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", border: "1px solid var(--glass-border)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                      <div>
                        <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Max cost per grading session ($)</label>
                        <input
                          type="number"
                          className="input"
                          placeholder="e.g. 2.00"
                          min="0"
                          step="0.01"
                          value={config.cost_limit_per_session || ""}
                          onChange={(e) => setConfig((prev) => ({ ...prev, cost_limit_per_session: parseFloat(e.target.value) || 0 }))}
                          style={{ width: "100%" }}
                        />
                      </div>
                      <div>
                        <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Monthly API budget ($)</label>
                        <input
                          type="number"
                          className="input"
                          placeholder="e.g. 25.00"
                          min="0"
                          step="0.01"
                          value={config.cost_limit_monthly || ""}
                          onChange={(e) => setConfig((prev) => ({ ...prev, cost_limit_monthly: parseFloat(e.target.value) || 0 }))}
                          style={{ width: "100%" }}
                        />
                      </div>
                    </div>
                    <div style={{ marginBottom: "12px" }}>
                      <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Warning threshold</label>
                      <select
                        className="input"
                        value={config.cost_warning_pct || 80}
                        onChange={(e) => setConfig((prev) => ({ ...prev, cost_warning_pct: parseInt(e.target.value) }))}
                        style={{ width: "auto", cursor: "pointer" }}
                      >
                        <option value={50}>50%</option>
                        <option value={60}>60%</option>
                        <option value={70}>70%</option>
                        <option value={80}>80%</option>
                        <option value={90}>90%</option>
                      </select>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Set to 0 for no limit. Session limit auto-stops grading when reached.
                    </p>
                  </div>
                </div>

                {/* Unified Cost Summary */}
                <div style={{ marginTop: "30px" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="BarChart3" size={20} style={{ color: "#10b981" }} />
                    API Usage Summary
                  </h3>
                  {!costSummary ? (
                    <button
                      onClick={async () => {
                        try {
                          const [analyticsRes, plannerRes, assistantRes] = await Promise.all([
                            api.getAnalytics().catch(() => null),
                            api.getPlannerCosts().catch(() => null),
                            api.getAssistantCosts().catch(() => null),
                          ]);
                          setCostSummary({
                            grading: analyticsRes?.cost_summary || { total_cost: 0, total_graded: 0, avg_cost_per_student: 0 },
                            planner: plannerRes?.total || { total_cost: 0, api_calls: 0 },
                            assistant: assistantRes?.total || { total_cost: 0, api_calls: 0 },
                          });
                        } catch {
                          setCostSummary({ grading: { total_cost: 0 }, planner: { total_cost: 0 }, assistant: { total_cost: 0 } });
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="RefreshCw" size={14} />
                      Load Cost Summary
                    </button>
                  ) : (
                    <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", border: "1px solid var(--glass-border)" }}>
                      <div style={{ display: "grid", gap: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Grading</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.grading.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.grading.total_graded || 0} students</span>
                            <span>~${(costSummary.grading.avg_cost_per_student || 0).toFixed(4)}/student</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Assistant</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.assistant.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.assistant.api_calls || 0} API calls</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Planner</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.planner.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.planner.api_calls || 0} API calls</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 0", fontWeight: 700 }}>
                          <span style={{ fontSize: "0.9rem" }}>Total</span>
                          <span style={{ fontSize: "0.9rem", color: "#f59e0b" }}>
                            ${((costSummary.grading.total_cost || 0) + (costSummary.assistant.total_cost || 0) + (costSummary.planner.total_cost || 0)).toFixed(4)}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={async () => {
                          try {
                            const [analyticsRes, plannerRes, assistantRes] = await Promise.all([
                              api.getAnalytics().catch(() => null),
                              api.getPlannerCosts().catch(() => null),
                              api.getAssistantCosts().catch(() => null),
                            ]);
                            setCostSummary({
                              grading: analyticsRes?.cost_summary || { total_cost: 0, total_graded: 0, avg_cost_per_student: 0 },
                              planner: plannerRes?.total || { total_cost: 0, api_calls: 0 },
                              assistant: assistantRes?.total || { total_cost: 0, api_calls: 0 },
                            });
                          } catch { /* ignore */ }
                        }}
                        style={{ marginTop: "12px", padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.75rem" }}
                      >
                        Refresh
                      </button>
                    </div>
                  )}
                </div>
              </>
  );
}
