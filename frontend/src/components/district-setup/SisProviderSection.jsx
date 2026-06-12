import React from "react";
import { styles, sectionHeadingStyle } from "./theme";
import PasswordField from "./PasswordField";

// SIS Provider section (radio toggle + Clever/OneRoster credential fields +
// test/save). Markup moved verbatim from ConfigForm in DistrictSetup.jsx (CQ
// wave-5 split); all state stays in ConfigForm and arrives via props.
// Credential fields are write-only: secrets render blank with a "Saved" badge
// when the backend reports has_* — do not echo stored secret values here.
export default function SisProviderSection(props) {
  var isDark = props.isDark;
  var inputStyleThemed = props.inputStyleThemed;
  var radioLabelStyle = props.radioLabelStyle;
  var sisType = props.sisType;
  var setSisType = props.setSisType;
  var setSisSaved = props.setSisSaved;
  var config = props.config;
  var updateField = props.updateField;
  var hasKeys = props.hasKeys;
  var showSecrets = props.showSecrets;
  var toggleSecret = props.toggleSecret;
  var applyPreset = props.applyPreset;
  var handleTestConnection = props.handleTestConnection;
  var handleSaveSIS = props.handleSaveSIS;
  var testing = props.testing;
  var saving = props.saving;
  var sisSaved = props.sisSaved;
  var testResult = props.testResult;

  return React.createElement(React.Fragment, null,
    // Section 1: SIS Provider
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "SIS Provider"),
    React.createElement("div", { style: styles.radioGroup },
      React.createElement("label", { style: radioLabelStyle },
        React.createElement("input", {
          type: "radio",
          name: "sis_type",
          value: "clever",
          checked: sisType === "clever",
          onChange: function() { setSisType("clever"); setSisSaved(false); },
        }),
        "Clever"
      ),
      React.createElement("label", { style: radioLabelStyle },
        React.createElement("input", {
          type: "radio",
          name: "sis_type",
          value: "oneroster",
          checked: sisType === "oneroster",
          onChange: function() { setSisType("oneroster"); setSisSaved(false); },
        }),
        "OneRoster"
      )
    ),

    // Clever fields
    sisType === "clever" ? React.createElement(React.Fragment, null,
      React.createElement("label", { style: styles.label }, "Client ID"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.clever_client_id,
        onChange: function(e) { updateField("clever_client_id", e.target.value); },
        placeholder: "Clever application client ID",
      }),
      React.createElement("label", { style: styles.label },
        "Client Secret",
        hasKeys.has_clever_secret ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, { isDark: isDark,
        value: config.clever_client_secret,
        onChange: function(e) { updateField("clever_client_secret", e.target.value); },
        placeholder: hasKeys.has_clever_secret ? "Leave blank to keep current" : "Clever client secret",
        show: !!showSecrets.clever_secret,
        setShow: function() { toggleSecret("clever_secret"); },
      }),
      React.createElement("label", { style: styles.label }, "Redirect URI"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.clever_redirect_uri,
        onChange: function(e) { updateField("clever_redirect_uri", e.target.value); },
        placeholder: "https://app.graider.live/api/clever/callback",
      }),
      React.createElement("label", { style: styles.label },
        "District Token (optional)",
        hasKeys.has_clever_token ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, { isDark: isDark,
        value: config.clever_district_token,
        onChange: function(e) { updateField("clever_district_token", e.target.value); },
        placeholder: hasKeys.has_clever_token ? "Leave blank to keep current" : "For Secure Sync (optional)",
        show: !!showSecrets.clever_token,
        setShow: function() { toggleSecret("clever_token"); },
      })
    ) : null,

    // OneRoster fields
    sisType === "oneroster" ? React.createElement(React.Fragment, null,
      React.createElement("label", { style: styles.label }, "Base URL"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.oneroster_base_url,
        onChange: function(e) { updateField("oneroster_base_url", e.target.value); },
        placeholder: "https://sis.district.org/ims/oneroster/v1p1",
      }),
      React.createElement("label", { style: styles.label }, "Client ID"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.oneroster_client_id,
        onChange: function(e) { updateField("oneroster_client_id", e.target.value); },
        placeholder: "OAuth 2.0 client ID",
      }),
      React.createElement("label", { style: styles.label },
        "Client Secret",
        hasKeys.has_oneroster_secret ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, { isDark: isDark,
        value: config.oneroster_client_secret,
        onChange: function(e) { updateField("oneroster_client_secret", e.target.value); },
        placeholder: hasKeys.has_oneroster_secret ? "Leave blank to keep current" : "OAuth 2.0 client secret",
        show: !!showSecrets.oneroster_secret,
        setShow: function() { toggleSecret("oneroster_secret"); },
      }),
      React.createElement("label", { style: styles.label }, "Token URL (optional)"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.oneroster_token_url,
        onChange: function(e) { updateField("oneroster_token_url", e.target.value); },
        placeholder: "Auto-detected if blank",
      }),
      React.createElement("div", null,
        React.createElement("button", {
          type: "button",
          style: styles.presetBtn,
          onClick: function() { applyPreset("classlink"); },
        }, "ClassLink"),
        React.createElement("button", {
          type: "button",
          style: styles.presetBtn,
          onClick: function() { applyPreset("powerschool"); },
        }, "PowerSchool")
      ),
      React.createElement("label", { style: styles.label }, "School ID (optional)"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: config.oneroster_school_id,
        onChange: function(e) { updateField("oneroster_school_id", e.target.value); },
        placeholder: "sourcedId to scope roster",
      })
    ) : null,

    // Test + Save buttons for SIS
    React.createElement("div", { style: { display: "flex", gap: "10px", marginTop: "16px" } },
      React.createElement("button", {
        type: "button",
        style: Object.assign({}, styles.btnSmall, { flex: 1 }),
        onClick: handleTestConnection,
        disabled: testing,
      }, testing ? "Testing..." : "Test Connection"),
      React.createElement("button", {
        type: "button",
        style: Object.assign({}, styles.btnSmall, { flex: 1 }),
        onClick: handleSaveSIS,
        disabled: saving,
      }, saving ? "Saving..." : "Save SIS Config")
    ),
    sisSaved ? React.createElement("span", {
      style: Object.assign({}, styles.badge, styles.badgeGreen, { marginTop: "8px", display: "inline-block" }),
    }, "Saved") : null,
    testResult ? React.createElement("div", {
      style: testResult.error ? styles.error : styles.success,
    }, testResult.error ? "Error: " + testResult.error : "Connection successful") : null
  );
}
