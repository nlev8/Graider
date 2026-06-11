import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AssistantModelSection(props) {
  const { addToast, config, globalAINotes, setConfig } = props;
  return (
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
  );
}
