import React from "react";
import Icon from "../Icon";

export default function OpenAIKeyField(props) {
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
  );
}
