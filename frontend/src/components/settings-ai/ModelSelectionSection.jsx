import React from "react";
import Icon from "../Icon";

export default function ModelSelectionSection(props) {
  const { apiKeys, config, setConfig } = props;
  return (
              <>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Sparkles" size={20} style={{ color: "#8b5cf6" }} />
                AI Model
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                Choose which AI model to use for grading and assessment generation.
              </p>
              {(() => {
                const hasOwnKeys = apiKeys.openaiIsOwn || apiKeys.anthropicIsOwn || apiKeys.geminiIsOwn;
                return (
                  <select
                    className="input"
                    value={config.ai_model}
                    onChange={(e) =>
                      setConfig((prev) => ({
                        ...prev,
                        ai_model: e.target.value,
                      }))
                    }
                    style={{ maxWidth: "350px" }}
                  >
                    <optgroup label="OpenAI">
                      <option value="gpt-4o-mini">
                        GPT-4o Mini (Fast & Cheap)
                      </option>
                      {hasOwnKeys && (
                        <option value="gpt-4o">
                          GPT-4o (Best Quality)
                        </option>
                      )}
                    </optgroup>
                    {hasOwnKeys && (
                      <optgroup label="Anthropic">
                        <option value="claude-haiku">
                          Claude Haiku (Fast & Cheap)
                        </option>
                        <option value="claude-sonnet">
                          Claude Sonnet (Balanced)
                        </option>
                        <option value="claude-opus">
                          Claude Opus (Most Capable)
                        </option>
                      </optgroup>
                    )}
                    <optgroup label="Google">
                      <option value="gemini-flash">
                        Gemini 2.0 Flash (Fast & Cheap)
                      </option>
                      {hasOwnKeys && (
                        <option value="gemini-pro">
                          Gemini 2.0 Pro (Balanced)
                        </option>
                      )}
                    </optgroup>
                    {!hasOwnKeys && (
                      <option disabled value="" style={{ fontStyle: "italic", color: "var(--text-muted)" }}>
                        Add your own API keys in Settings to unlock more models
                      </option>
                    )}
                  </select>
                );
              })()}
              <p
                style={{
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                  marginTop: "10px",
                  padding: "10px 14px",
                  background: (() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "rgba(74,222,128,0.1)" : "rgba(245,158,11,0.1)";
                  })(),
                  borderRadius: "8px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon
                  name={(() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "CheckCircle" : "AlertCircle";
                  })()}
                  size={16}
                  style={{ color: (() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "#4ade80" : "#f59e0b";
                  })() }}
                />
                {config.ai_model?.startsWith("claude")
                  ? apiKeys.anthropicConfigured
                    ? "Anthropic API connected"
                    : "Add Anthropic API key below to use Claude"
                  : config.ai_model?.startsWith("gemini")
                    ? apiKeys.geminiConfigured
                      ? "Google AI API connected"
                      : "Add Google AI API key below to use Gemini"
                    : apiKeys.openaiConfigured
                      ? "OpenAI API connected"
                      : "Add OpenAI API key below to use GPT"}
              </p>
              </>
  );
}
