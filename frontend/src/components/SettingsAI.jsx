import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";
import { getAuthHeaders } from "../services/api";

export default function SettingsAI({ MODEL_COST_PER_ASSIGNMENT, addToast, apiKeys, config, globalAINotes, savingApiKeys, setApiKeys, setConfig, setGlobalAINotes, setSavingApiKeys, setShowApiKeys, showApiKeys }) {
  return (
              <>
            {/* AI Model Selection */}
            <div data-tutorial="settings-ai">
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

              {/* Extraction Mode Toggle - A/B Test */}
              <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                <div style={{ marginBottom: "10px" }}>
                  <span style={{ fontWeight: 600 }}>
                    <Icon name="FileSearch" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    Response Extraction Mode
                  </span>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "structured" ? "rgba(59, 130, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "structured" ? "1px solid rgba(59, 130, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="structured"
                      checked={config.extraction_mode === "structured"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>Structured</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Parse with rules</div>
                    </div>
                  </label>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "ai" ? "rgba(139, 92, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "ai" ? "1px solid rgba(139, 92, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="ai"
                      checked={config.extraction_mode === "ai"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>AI-Powered</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Let AI identify responses</div>
                    </div>
                  </label>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "10px" }}>
                  {config.extraction_mode === "structured"
                    ? "Uses parsing rules to separate questions from answers. More predictable but may miss edge cases."
                    : "Sends raw content to AI and lets it identify what's a prompt vs student response. More flexible."}
                </p>
              </div>

              {/* Ensemble Grading Toggle */}
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
            </div>

            {/* Global AI Instructions */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="MessageSquare" size={20} style={{ color: "#6366f1" }} />
                Global AI Instructions
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                These instructions apply to both grading AND assessment generation. Include differentiation rules for periods here.
              </p>
              <textarea
                className="input"
                value={globalAINotes}
                onChange={(e) => setGlobalAINotes(e.target.value)}
                placeholder="Example: For assessment generation, Periods 1,2,5 are advanced (7th-8th grade level). Periods 4,6,7 should be 6th grade level only."
                style={{ minHeight: "120px", resize: "vertical" }}
              />
            </div>

            {/* API Keys Section */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="Key" size={20} style={{ color: "#f59e0b" }} />
                API Keys
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Connect your AI provider API keys. Keys are stored
                securely and never shared.
              </p>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "15px",
                }}
              >
                {/* OpenAI API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    OpenAI API Key
                    {apiKeys.openaiConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={showApiKeys.openai ? "text" : "password"}
                        className="input"
                        value={apiKeys.openai}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            openai: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.openaiConfigured
                            ? "••••••••••••••••"
                            : "sk-..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            openai: !prev.openai,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={showApiKeys.openai ? "EyeOff" : "Eye"}
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://platform.openai.com/api-keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      platform.openai.com
                    </a>
                  </p>
                </div>

                {/* Anthropic API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    Anthropic (Claude) API Key
                    {apiKeys.anthropicConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={
                          showApiKeys.anthropic ? "text" : "password"
                        }
                        className="input"
                        value={apiKeys.anthropic}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            anthropic: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.anthropicConfigured
                            ? "••••••••••••••••"
                            : "sk-ant-..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            anthropic: !prev.anthropic,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={
                            showApiKeys.anthropic ? "EyeOff" : "Eye"
                          }
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://console.anthropic.com/settings/keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      console.anthropic.com
                    </a>
                  </p>
                </div>

                {/* Google AI (Gemini) API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    Google AI (Gemini) API Key
                    {apiKeys.geminiConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={
                          showApiKeys.gemini ? "text" : "password"
                        }
                        className="input"
                        value={apiKeys.gemini}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            gemini: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.geminiConfigured
                            ? "••••••••••••••••"
                            : "AIza..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            gemini: !prev.gemini,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={
                            showApiKeys.gemini ? "EyeOff" : "Eye"
                          }
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://aistudio.google.com/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      aistudio.google.com
                    </a>
                  </p>
                </div>

                <button
                  onClick={async () => {
                    setSavingApiKeys(true);
                    try {
                      const authHdrs = await getAuthHeaders();
                      const response = await fetch(
                        "/api/save-api-keys",
                        {
                          method: "POST",
                          headers: {
                            "Content-Type": "application/json",
                            ...authHdrs,
                          },
                          body: JSON.stringify({
                            openai_key: apiKeys.openai || undefined,
                            anthropic_key: apiKeys.anthropic || undefined,
                            gemini_key: apiKeys.gemini || undefined,
                          }),
                        },
                      );
                      const data = await response.json();
                      if (data.status === "success") {
                        setApiKeys((prev) => ({
                          ...prev,
                          openai: "",
                          anthropic: "",
                          gemini: "",
                          openaiConfigured: data.openai_configured,
                          anthropicConfigured: data.anthropic_configured,
                          geminiConfigured: data.gemini_configured,
                        }));
                        addToast(
                          "API keys saved successfully",
                          "success",
                        );
                      } else {
                        addToast(
                          data.error || "Failed to save API keys",
                          "error",
                        );
                      }
                    } catch (err) {
                      addToast(
                        "Error saving API keys: " + err.message,
                        "error",
                      );
                    } finally {
                      setSavingApiKeys(false);
                    }
                  }}
                  disabled={
                    savingApiKeys ||
                    (!apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini)
                  }
                  className="btn btn-primary"
                  style={{
                    alignSelf: "flex-start",
                    opacity:
                      !apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini ? 0.5 : 1,
                  }}
                >
                  {savingApiKeys ? "Saving..." : "Save API Keys"}
                </button>
              </div>
            </div>

            {/* Assistant Model Selection */}
            <div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                marginBottom: "15px",
                marginTop: "25px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}>
                <Icon name="Sparkles" size={20} style={{ color: "#6366f1" }} />
                AI Assistant Model
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                Choose which AI model powers the Teaching Assistant chat.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <select
                  className="input"
                  style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                  value={config.assistant_model || "haiku"}
                  onChange={(e) => {
                    var updated = { ...config, assistant_model: e.target.value };
                    setConfig(updated);
                    api.saveGlobalSettings({ globalAINotes, config: updated }).then(() => {
                      var labels = {
                        "haiku": "Haiku 4.5 (fast, low cost)",
                        "sonnet": "Sonnet 4 (higher quality)",
                        "gpt-4o-mini": "GPT-4o Mini (fast, low cost)",
                        "gpt-4o": "GPT-4o (best quality)",
                        "gemini-flash": "Gemini Flash (fast, low cost)",
                        "gemini-pro": "Gemini Pro (balanced)"
                      };
                      addToast("Assistant model set to " + (labels[e.target.value] || e.target.value), "success");
                    });
                  }}
                >
                  <optgroup label="Anthropic">
                    <option value="haiku">Haiku 4.5 — Fast, low cost ($0.80/$4 per 1M tokens)</option>
                    <option value="sonnet">Sonnet 4 — Higher quality ($3/$15 per 1M tokens)</option>
                  </optgroup>
                  <optgroup label="OpenAI">
                    <option value="gpt-4o-mini">GPT-4o Mini — Fast, low cost ($0.15/$0.60 per 1M tokens)</option>
                    <option value="gpt-4o">GPT-4o — Best quality ($2.50/$10 per 1M tokens)</option>
                  </optgroup>
                  <optgroup label="Google">
                    <option value="gemini-flash">Gemini 2.0 Flash — Fast, low cost ($0.10/$0.40 per 1M tokens)</option>
                    <option value="gemini-pro">Gemini 2.0 Pro — Balanced ($1.25/$5 per 1M tokens)</option>
                  </optgroup>
                </select>
              </div>
            </div>

            {/* Assistant Voice Selection */}
            <div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                marginBottom: "15px",
                marginTop: "25px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}>
                <Icon name="Mic" size={20} style={{ color: "#6366f1" }} />
                Assistant Voice
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                Choose the voice used for voice-mode responses.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <select
                  className="input"
                  style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                  value={config.assistant_voice || "nova"}
                  onChange={(e) => {
                    var updated = { ...config, assistant_voice: e.target.value };
                    setConfig(updated);
                    api.saveGlobalSettings({ globalAINotes, config: updated }).then(() => {
                      addToast("Voice set to " + e.target.value.charAt(0).toUpperCase() + e.target.value.slice(1), "success");
                    });
                  }}
                >
                  <option value="alloy">Alloy — Neutral, balanced</option>
                  <option value="ash">Ash — Warm, conversational</option>
                  <option value="coral">Coral — Friendly, expressive</option>
                  <option value="echo">Echo — Smooth, articulate</option>
                  <option value="fable">Fable — Storytelling, animated</option>
                  <option value="nova">Nova — Bright, engaging (default)</option>
                  <option value="onyx">Onyx — Deep, authoritative</option>
                  <option value="sage">Sage — Calm, thoughtful</option>
                  <option value="shimmer">Shimmer — Light, cheerful</option>
                </select>
              </div>
            </div>

              </>
  );
}
