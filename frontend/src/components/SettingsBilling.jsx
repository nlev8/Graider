import React from "react";
import Icon from "./Icon";
import BillingPlanCard from "./BillingPlanCard";
import ApiUsageSummary from "./ApiUsageSummary";

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

                  <BillingPlanCard
                    addToast={addToast}
                    setSubscription={setSubscription}
                    setSubscriptionLoading={setSubscriptionLoading}
                    subscription={subscription}
                    subscriptionLoading={subscriptionLoading}
                  />
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
                  <ApiUsageSummary costSummary={costSummary} setCostSummary={setCostSummary} />
                </div>
              </>
  );
}
