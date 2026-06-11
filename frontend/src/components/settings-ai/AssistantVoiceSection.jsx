import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AssistantVoiceSection(props) {
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
  );
}
