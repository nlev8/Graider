import React from "react";
import Icon from "../Icon";

export default function GeminiKeyField(props) {
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
  );
}
