import React from "react";
import { styles, sectionHeadingStyle } from "./theme";
import PasswordField from "./PasswordField";

// AI API Keys section. Markup moved verbatim from ConfigForm in
// DistrictSetup.jsx (CQ wave-5 split); state stays in ConfigForm. Key fields
// are write-only: saved keys render blank with a "Saved" badge (has_*) and
// "Leave blank to keep current" — stored key material is never echoed.
// The shared save-error line stays in ConfigForm (it is shared with the SIS
// save handler), so this section renders only the keysSaved badge.
export default function AiKeysSection(props) {
  var isDark = props.isDark;
  var config = props.config;
  var updateField = props.updateField;
  var hasKeys = props.hasKeys;
  var showSecrets = props.showSecrets;
  var toggleSecret = props.toggleSecret;
  var handleSaveKeys = props.handleSaveKeys;
  var saving = props.saving;
  var keysSaved = props.keysSaved;

  return React.createElement(React.Fragment, null,
    // Section 2: AI API Keys
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "AI API Keys"),
    React.createElement("div", { style: styles.helperText }, "Teachers can override with their own keys in Settings"),

    React.createElement("label", { style: styles.label },
      "OpenAI API Key",
      hasKeys.has_openai ? React.createElement("span", {
        style: Object.assign({}, styles.badge, styles.badgeGreen),
      }, "Saved") : null
    ),
    React.createElement(PasswordField, { isDark: isDark,
      value: config.openai_api_key,
      onChange: function(e) { updateField("openai_api_key", e.target.value); },
      placeholder: hasKeys.has_openai ? "Leave blank to keep current" : "sk-...",
      show: !!showSecrets.openai,
      setShow: function() { toggleSecret("openai"); },
    }),

    React.createElement("label", { style: styles.label },
      "Anthropic API Key",
      hasKeys.has_anthropic ? React.createElement("span", {
        style: Object.assign({}, styles.badge, styles.badgeGreen),
      }, "Saved") : null
    ),
    React.createElement(PasswordField, { isDark: isDark,
      value: config.anthropic_api_key,
      onChange: function(e) { updateField("anthropic_api_key", e.target.value); },
      placeholder: hasKeys.has_anthropic ? "Leave blank to keep current" : "sk-ant-...",
      show: !!showSecrets.anthropic,
      setShow: function() { toggleSecret("anthropic"); },
    }),

    React.createElement("label", { style: styles.label },
      "Gemini API Key",
      hasKeys.has_gemini ? React.createElement("span", {
        style: Object.assign({}, styles.badge, styles.badgeGreen),
      }, "Saved") : null
    ),
    React.createElement(PasswordField, { isDark: isDark,
      value: config.gemini_api_key,
      onChange: function(e) { updateField("gemini_api_key", e.target.value); },
      placeholder: hasKeys.has_gemini ? "Leave blank to keep current" : "AIza...",
      show: !!showSecrets.gemini,
      setShow: function() { toggleSecret("gemini"); },
    }),

    React.createElement("button", {
      type: "button",
      style: styles.btnSmall,
      onClick: handleSaveKeys,
      disabled: saving,
    }, saving ? "Saving..." : "Save Keys"),
    keysSaved ? React.createElement("span", {
      style: Object.assign({}, styles.badge, styles.badgeGreen, { marginLeft: "10px" }),
    }, "Saved") : null
  );
}
