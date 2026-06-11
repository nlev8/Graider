import React from "react";
import Icon from "../Icon";

export default function AnthropicKeyField(props) {
  const { apiKeys, setApiKeys, setShowApiKeys, showApiKeys } = props;
  return (
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
  );
}
