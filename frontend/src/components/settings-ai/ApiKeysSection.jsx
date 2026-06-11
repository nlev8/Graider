import React from "react";
import Icon from "../Icon";
import { getAuthHeaders } from "../../services/api";
import OpenAIKeyField from "./OpenAIKeyField";
import AnthropicKeyField from "./AnthropicKeyField";
import GeminiKeyField from "./GeminiKeyField";

export default function ApiKeysSection(props) {
  const { addToast, apiKeys, savingApiKeys, setApiKeys, setSavingApiKeys } = props;
  return (
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
                <OpenAIKeyField {...props} />

                {/* Anthropic API Key */}
                <AnthropicKeyField {...props} />

                {/* Google AI (Gemini) API Key */}
                <GeminiKeyField {...props} />

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
  );
}
