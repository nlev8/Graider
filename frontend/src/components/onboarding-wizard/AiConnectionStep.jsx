import Icon from "../Icon";

// Step 5 — AI Connection. Stateless: showExtraKeys / savingKeys / wizardData all
// live in the shell so the disclosure + key drafts survive Back/Next navigation.
export default function AiConnectionStep(props) {
  const {
    wizardData,
    updateField,
    apiKeys,
    isCleverUser,
    hasAnyApiKey,
    showExtraKeys,
    setShowExtraKeys,
    savingKeys,
  } = props;

  const renderKeyInput = (label, field, configured, helpUrl, helpDomain) => (
    <div style={{ marginBottom: 16 }}>
      <label className="label" style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 8 }}>
        {label}
        {configured && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#22c55e", fontSize: "0.8rem", fontWeight: 500 }}>
            <Icon name="CheckCircle" size={14} style={{ color: "#22c55e" }} /> Configured
          </span>
        )}
      </label>
      <input
        className="input"
        type="password"
        placeholder={configured ? "Key already saved (enter new to replace)" : "Paste your API key here"}
        value={wizardData[field]}
        onChange={(e) => updateField(field, e.target.value)}
      />
      <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>
        Get your key from{" "}
        <a
          href={helpUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--accent-primary)" }}
        >
          {helpDomain}
        </a>
      </p>
    </div>
  );

  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>AI Connection</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.95rem" }}>
        {isCleverUser
          ? "Your district may have pre-configured API keys. If not, you can add your own below or skip this step."
          : "Graider uses AI to grade assignments. You need at least one API key to continue."}
      </p>

      {isCleverUser && hasAnyApiKey && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 14px", borderRadius: 8, marginBottom: 16,
          background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)",
          fontSize: "0.88rem", color: "#22c55e",
        }}>
          <Icon name="CheckCircle" size={16} />
          AI provider is configured. You're all set!
        </div>
      )}

      {isCleverUser && !hasAnyApiKey && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 14px", borderRadius: 8, marginBottom: 16,
          background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)",
          fontSize: "0.88rem", color: "#f59e0b",
        }}>
          <Icon name="AlertTriangle" size={16} />
          No API key configured yet. Add one below, or your district admin can set this up for you.
        </div>
      )}

      <div style={{
        background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
        borderRadius: 12, padding: 16, marginBottom: 20,
      }}>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--accent-primary)", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>
          How to get an OpenAI API key (2 minutes)
        </div>
        {[
          { num: "1", icon: "ExternalLink", text: <>Go to <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent-primary)" }}>platform.openai.com</a> and sign up or log in</> },
          { num: "2", icon: "CreditCard", text: "Add a payment method under Billing (API usage costs ~$0.01-0.03 per assignment)" },
          { num: "3", icon: "Key", text: "Go to API Keys, click \"Create new secret key\", and copy it" },
          { num: "4", icon: "ClipboardPaste", text: "Paste the key below" },
        ].map(function(s) {
          return (
            <div key={s.num} style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: "rgba(99,102,241,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, marginTop: 1,
              }}>
                <Icon name={s.icon} size={14} style={{ color: "var(--accent-primary)" }} />
              </div>
              <span style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {s.text}
              </span>
            </div>
          );
        })}
      </div>

      {renderKeyInput(
        "OpenAI API Key (Recommended)",
        "openai_key",
        apiKeys.openaiConfigured,
        "https://platform.openai.com/api-keys",
        "platform.openai.com"
      )}

      <button
        onClick={() => setShowExtraKeys(!showExtraKeys)}
        style={{
          background: "none", border: "none", cursor: "pointer",
          color: "var(--text-secondary)", fontSize: "0.85rem",
          display: "flex", alignItems: "center", gap: 6,
          padding: "4px 0", marginBottom: showExtraKeys ? 12 : 0,
        }}
      >
        <Icon name={showExtraKeys ? "ChevronUp" : "ChevronDown"} size={14} />
        {showExtraKeys ? "Hide" : "Show"} additional providers
      </button>

      {showExtraKeys && (
        <>
          {renderKeyInput(
            "Anthropic API Key",
            "anthropic_key",
            apiKeys.anthropicConfigured,
            "https://console.anthropic.com/settings/keys",
            "console.anthropic.com"
          )}
          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: -10, marginBottom: 16, paddingLeft: 2 }}>
            Sign up at <a href="https://console.anthropic.com" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent-primary)" }}>console.anthropic.com</a>, add billing, then go to API Keys to create one.
          </div>
          {renderKeyInput(
            "Google Gemini API Key (Free Tier Available)",
            "gemini_key",
            apiKeys.geminiConfigured,
            "https://aistudio.google.com/apikey",
            "aistudio.google.com"
          )}
          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: -10, marginBottom: 8, paddingLeft: 2 }}>
            Sign in with Google at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent-primary)" }}>aistudio.google.com</a> and click "Create API Key." No credit card required.
          </div>
        </>
      )}

      {!hasAnyApiKey && !isCleverUser && (
        <div style={{
          marginTop: 16, padding: "12px 16px",
          background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: 8, fontSize: "0.85rem",
          color: "var(--text-secondary)",
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <Icon name="AlertCircle" size={18} style={{ color: "#ef4444", flexShrink: 0, marginTop: 1 }} />
          <div>
            An API key is required to use Graider. Paste at least one key above to continue.
          </div>
        </div>
      )}

      {savingKeys && (
        <div style={{ marginTop: 12, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Saving keys...
        </div>
      )}
    </div>
  );
}
