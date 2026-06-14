import React from "react";
import Icon from "../Icon";

export default function OneRosterCredentialsFields({ oneRosterConfig, oneRosterHasCredentials, setOneRosterConfig, setShowOneRosterSecret, showOneRosterSecret }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "500px" }}>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Base URL *</label>
        <input
          type="text"
          value={oneRosterConfig.base_url}
          onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { base_url: e.target.value }); }); }}
          placeholder="https://yoursis.example.com/ims/oneroster/v1p1"
          style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
        />
      </div>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Client ID *</label>
        <input
          type="text"
          value={oneRosterConfig.client_id}
          onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { client_id: e.target.value }); }); }}
          placeholder="OAuth 2.0 Client ID"
          style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
        />
      </div>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
          Client Secret *
          {oneRosterHasCredentials && !oneRosterConfig.client_secret && (
            <span style={{ marginLeft: "8px", padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600, background: "rgba(34,197,94,0.15)", color: "#22c55e" }}>
              Credentials saved
            </span>
          )}
        </label>
        <div style={{ position: "relative" }}>
          <input
            type={showOneRosterSecret ? "text" : "password"}
            value={oneRosterConfig.client_secret}
            onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { client_secret: e.target.value }); }); }}
            placeholder={oneRosterHasCredentials ? "Leave blank to keep existing" : "OAuth 2.0 Client Secret"}
            style={{ width: "100%", padding: "10px 14px", paddingRight: "44px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
          />
          <button type="button" onClick={function() { setShowOneRosterSecret(function(p) { return !p; }); }} style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: "4px", color: "var(--text-secondary)", display: "flex", alignItems: "center" }} title={showOneRosterSecret ? "Hide secret" : "Show secret"}>
            <Icon name={showOneRosterSecret ? "EyeOff" : "Eye"} size={18} />
          </button>
        </div>
      </div>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Token URL (optional)</label>
        <input
          type="text"
          value={oneRosterConfig.token_url}
          onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { token_url: e.target.value }); }); }}
          placeholder="Defaults to base_url/token"
          style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
        />
      </div>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>School ID (optional)</label>
        <input
          type="text"
          value={oneRosterConfig.school_id}
          onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { school_id: e.target.value }); }); }}
          placeholder="Filter roster to a specific school"
          style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
        />
      </div>
      <div>
        <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Teacher Sourced ID *</label>
        <input
          type="text"
          value={oneRosterConfig.teacher_sourced_id}
          onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { teacher_sourced_id: e.target.value }); }); }}
          placeholder="Your OneRoster teacher sourcedId"
          style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
        />
      </div>
    </div>
  );
}
