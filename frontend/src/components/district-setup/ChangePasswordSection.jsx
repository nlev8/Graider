import React from "react";
import { styles } from "./theme";

// Change Password block (collapsed behind a toggle button). Markup moved
// verbatim from ConfigForm in DistrictSetup.jsx (CQ wave-5 split); the
// password fields + messages state stays in the always-mounted ConfigForm so
// nothing is lost while this block toggles open/closed.
export default function ChangePasswordSection(props) {
  var inputStyleThemed = props.inputStyleThemed;
  var showChangePw = props.showChangePw;
  var setShowChangePw = props.setShowChangePw;
  var setPwMsg = props.setPwMsg;
  var setPwErr = props.setPwErr;
  var currentPw = props.currentPw;
  var setCurrentPw = props.setCurrentPw;
  var newPw = props.newPw;
  var setNewPw = props.setNewPw;
  var handleChangePassword = props.handleChangePassword;
  var pwMsg = props.pwMsg;
  var pwErr = props.pwErr;

  return React.createElement("div", { style: { marginTop: "20px" } },
    React.createElement("button", {
      type: "button",
      style: styles.btnOutline,
      onClick: function() { setShowChangePw(!showChangePw); setPwMsg(""); setPwErr(""); },
    }, showChangePw ? "Cancel" : "Change Password"),
    showChangePw ? React.createElement("div", { style: { marginTop: "12px" } },
      React.createElement("label", { style: styles.label }, "Current Password"),
      React.createElement("input", {
        type: "password",
        style: inputStyleThemed,
        value: currentPw,
        onChange: function(e) { setCurrentPw(e.target.value); },
      }),
      React.createElement("label", { style: styles.label }, "New Password"),
      React.createElement("input", {
        type: "password",
        style: inputStyleThemed,
        value: newPw,
        onChange: function(e) { setNewPw(e.target.value); },
        placeholder: "Min 8 characters",
      }),
      React.createElement("button", {
        type: "button",
        style: styles.btnSmall,
        onClick: handleChangePassword,
      }, "Update Password"),
      pwMsg ? React.createElement("div", { style: styles.success }, pwMsg) : null,
      pwErr ? React.createElement("div", { style: styles.error }, pwErr) : null
    ) : null
  );
}
