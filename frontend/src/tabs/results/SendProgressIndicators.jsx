import React from "react";
import * as api from "../../services/api";

export default function SendProgressIndicators({ outlookSendStatus, focusCommsStatus }) {
  return (
    <>
                    {/* Outlook Send Progress */}
                    {outlookSendStatus.status === "running" && (
                      <div style={{
                        padding: "12px 16px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--glass-border)",
                        marginTop: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.85rem", marginBottom: "6px", color: "var(--text-secondary)" }}>
                            {outlookSendStatus.message}
                          </div>
                          <div style={{ height: "6px", background: "var(--glass-border)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: (outlookSendStatus.total > 0 ? (outlookSendStatus.sent / outlookSendStatus.total * 100) : 0) + "%",
                              background: "var(--primary)",
                              borderRadius: "3px",
                              transition: "width 0.3s ease",
                            }} />
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                            {outlookSendStatus.sent + " of " + outlookSendStatus.total + " sent"}
                            {outlookSendStatus.failed > 0 ? " (" + outlookSendStatus.failed + " failed)" : ""}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Focus Comms Send Progress */}
                    {focusCommsStatus.status === "running" && (
                      <div style={{
                        padding: "12px 16px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--glass-border)",
                        marginTop: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.85rem", marginBottom: "6px", color: "var(--text-secondary)" }}>
                            {"Focus: " + focusCommsStatus.message}
                          </div>
                          <div style={{ height: "6px", background: "var(--glass-border)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: (focusCommsStatus.total > 0 ? (focusCommsStatus.sent / focusCommsStatus.total * 100) : 0) + "%",
                              background: "#10b981",
                              borderRadius: "3px",
                              transition: "width 0.3s ease",
                            }} />
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                            {focusCommsStatus.sent + " of " + focusCommsStatus.total + " sent"}
                            {focusCommsStatus.failed > 0 ? " (" + focusCommsStatus.failed + " failed)" : ""}
                          </div>
                        </div>
                        <button onClick={() => { api.stopFocusComms(); }} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>Stop</button>
                      </div>
                    )}
    </>
  );
}
