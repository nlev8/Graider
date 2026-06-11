import React from "react";
import { styles } from "./theme";

// Moved verbatim from DistrictSetup.jsx (CQ wave-5 split). Controlled
// show/hide password input; `show`/`setShow` are owned by the caller so a
// single toggle can drive paired fields (e.g. password + confirm).
export default function PasswordField(props) {
  var show = props.show;
  var setShow = props.setShow;
  var isDark = props.isDark !== false;
  var pfInput = isDark ? styles.input : Object.assign({}, styles.input, { background: "#f9f9f9", border: "1px solid #ddd", color: "#333" });
  return React.createElement("div", { style: styles.passwordWrap },
    React.createElement("input", {
      type: show ? "text" : "password",
      value: props.value,
      onChange: props.onChange,
      placeholder: props.placeholder || "",
      style: Object.assign({}, pfInput, { paddingRight: "60px" }),
      autoComplete: props.autoComplete || "off",
    }),
    React.createElement("button", {
      type: "button",
      style: styles.toggleBtn,
      onClick: function() { setShow(!show); },
    }, show ? "Hide" : "Show")
  );
}
