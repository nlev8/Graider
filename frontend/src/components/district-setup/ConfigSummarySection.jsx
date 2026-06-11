import React from "react";
import { styles, sectionHeadingStyle } from "./theme";

// Configuration Summary section. Markup moved verbatim from ConfigForm in
// DistrictSetup.jsx (CQ wave-5 split). Read-only rollup: reports
// configured/not-set per integration — never the credential values
// themselves.
export default function ConfigSummarySection(props) {
  var isDark = props.isDark;
  var sisType = props.sisType;
  var config = props.config;
  var hasKeys = props.hasKeys;

  return React.createElement(React.Fragment, null,
    // Section 4: Configuration Summary
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "Configuration Summary"),

    React.createElement("div", { style: styles.summaryItem },
      React.createElement("span", null, "SIS Provider"),
      React.createElement("span", { style: { fontWeight: "600" } }, sisType === "clever" ? "Clever" : "OneRoster")
    ),
    React.createElement("div", { style: styles.summaryItem },
      React.createElement("span", null, "SIS Credentials"),
      React.createElement("span", null,
        (sisType === "clever" ? (config.clever_client_id ? "Configured" : "Not set") : (config.oneroster_base_url ? "Configured" : "Not set"))
      )
    ),
    React.createElement("div", { style: styles.summaryItem },
      React.createElement("span", null, "OpenAI"),
      React.createElement("span", null, hasKeys.has_openai ? "Configured" : "Not set")
    ),
    React.createElement("div", { style: styles.summaryItem },
      React.createElement("span", null, "Anthropic"),
      React.createElement("span", null, hasKeys.has_anthropic ? "Configured" : "Not set")
    ),
    React.createElement("div", { style: styles.summaryItem },
      React.createElement("span", null, "Gemini"),
      React.createElement("span", null, hasKeys.has_gemini ? "Configured" : "Not set")
    )
  );
}
