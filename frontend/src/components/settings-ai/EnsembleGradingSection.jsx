import React from "react";
import Icon from "../Icon";

export default function EnsembleGradingSection(props) {
  const { MODEL_COST_PER_ASSIGNMENT, apiKeys, config, setConfig } = props;
  return (
              <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={config.ensemble_enabled}
                    onChange={(e) => setConfig((prev) => ({ ...prev, ensemble_enabled: e.target.checked }))}
                    style={{ width: "18px", height: "18px" }}
                  />
                  <span style={{ fontWeight: 600 }}>
                    <Icon name="Users" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    Ensemble Grading
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    (Grade with multiple AIs for accuracy)
                  </span>
                </label>

                {config.ensemble_enabled && (
                  <div style={{ marginTop: "15px" }}>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      Select 2-3 models to grade each assignment. Final score = median of all models.
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {[
                        { value: "gpt-4o-mini", label: "GPT-4o Mini", cost: "$0.001", provider: "openai" },
                        { value: "gpt-4o", label: "GPT-4o", cost: "$0.015", provider: "openai" },
                        { value: "claude-haiku", label: "Claude Haiku", cost: "$0.002", provider: "anthropic" },
                        { value: "claude-sonnet", label: "Claude Sonnet", cost: "$0.02", provider: "anthropic" },
                        { value: "gemini-flash", label: "Gemini Flash", cost: "$0.0005", provider: "gemini" },
                        { value: "gemini-pro", label: "Gemini Pro", cost: "$0.008", provider: "gemini" },
                      ].map((model) => {
                        const isConfigured = model.provider === "openai" ? apiKeys.openaiConfigured
                          : model.provider === "anthropic" ? apiKeys.anthropicConfigured
                          : apiKeys.geminiConfigured;
                        const isSelected = config.ensemble_models?.includes(model.value);
                        return (
                          <label
                            key={model.value}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              padding: "8px 12px",
                              borderRadius: "8px",
                              background: isSelected ? "rgba(139, 92, 246, 0.15)" : "transparent",
                              border: isSelected ? "1px solid rgba(139, 92, 246, 0.3)" : "1px solid transparent",
                              cursor: isConfigured ? "pointer" : "not-allowed",
                              opacity: isConfigured ? 1 : 0.5,
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              disabled={!isConfigured}
                              onChange={(e) => {
                                setConfig((prev) => {
                                  const models = prev.ensemble_models || [];
                                  if (e.target.checked) {
                                    return { ...prev, ensemble_models: [...models, model.value] };
                                  } else {
                                    return { ...prev, ensemble_models: models.filter((m) => m !== model.value) };
                                  }
                                });
                              }}
                              style={{ width: "16px", height: "16px" }}
                            />
                            <span style={{ flex: 1 }}>{model.label}</span>
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>~{model.cost}/assignment</span>
                            {!isConfigured && (
                              <span style={{ fontSize: "0.7rem", color: "#f59e0b" }}>No API key</span>
                            )}
                          </label>
                        );
                      })}
                    </div>
                    {config.ensemble_models?.length >= 2 && (
                      <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#4ade80" }}>
                        <Icon name="CheckCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                        {config.ensemble_models.length} models selected - estimated ~${(
                          config.ensemble_models.reduce((sum, m) => {
                            return sum + (MODEL_COST_PER_ASSIGNMENT[m] || 0);
                          }, 0)
                        ).toFixed(4)}/assignment
                      </p>
                    )}
                    {config.ensemble_models?.length === 1 && (
                      <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#f59e0b" }}>
                        <Icon name="AlertCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                        Select at least 2 models for ensemble grading
                      </p>
                    )}
                  </div>
                )}
              </div>
  );
}
