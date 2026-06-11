import * as api from "../../services/api";

// Handler bodies moved verbatim from ConfigForm in DistrictSetup.jsx (CQ
// wave-5 split). ConfigForm owns all state and calls this factory on every
// render with the current state values + setters, so each handler closes over
// exactly the same per-render values it did when defined inline (no
// memoization here, same as before the split — handlers were recreated each
// render then too).
export default function createConfigFormHandlers(ctx) {
  var config = ctx.config;
  var sisType = ctx.sisType;
  var currentPw = ctx.currentPw;
  var newPw = ctx.newPw;
  var onLogout = ctx.onLogout;
  var setConfig = ctx.setConfig;
  var setSisSaved = ctx.setSisSaved;
  var setKeysSaved = ctx.setKeysSaved;
  var setSaving = ctx.setSaving;
  var setError = ctx.setError;
  var setHasKeys = ctx.setHasKeys;
  var setTesting = ctx.setTesting;
  var setTestResult = ctx.setTestResult;
  var setShowSecrets = ctx.setShowSecrets;
  var setPwMsg = ctx.setPwMsg;
  var setPwErr = ctx.setPwErr;
  var setCurrentPw = ctx.setCurrentPw;
  var setNewPw = ctx.setNewPw;

  function updateField(field, value) {
    setConfig(function(prev) {
      var next = Object.assign({}, prev);
      next[field] = value;
      return next;
    });
    setSisSaved(false);
    setKeysSaved(false);
  }

  function toggleSecret(key) {
    setShowSecrets(function(prev) {
      var next = Object.assign({}, prev);
      next[key] = !prev[key];
      return next;
    });
  }

  function handleSaveSIS() {
    setSaving(true);
    setError("");
    setSisSaved(false);
    var payload = { sis_type: sisType };
    if (sisType === "clever") {
      payload.clever_client_id = config.clever_client_id;
      if (config.clever_client_secret) payload.clever_client_secret = config.clever_client_secret;
      payload.clever_redirect_uri = config.clever_redirect_uri;
      if (config.clever_district_token) payload.clever_district_token = config.clever_district_token;
    } else {
      payload.oneroster_base_url = config.oneroster_base_url;
      payload.oneroster_client_id = config.oneroster_client_id;
      if (config.oneroster_client_secret) payload.oneroster_client_secret = config.oneroster_client_secret;
      payload.oneroster_token_url = config.oneroster_token_url;
      payload.oneroster_school_id = config.oneroster_school_id;
    }
    api.saveDistrictConfig(payload).then(function(res) {
      setSaving(false);
      if (res && res.error) {
        setError(res.error);
      } else {
        setSisSaved(true);
        // Update has_keys indicators
        if (sisType === "clever") {
          setHasKeys(function(prev) {
            return Object.assign({}, prev, {
              has_clever_secret: prev.has_clever_secret || !!config.clever_client_secret,
              has_clever_token: prev.has_clever_token || !!config.clever_district_token,
            });
          });
        } else {
          setHasKeys(function(prev) {
            return Object.assign({}, prev, {
              has_oneroster_secret: prev.has_oneroster_secret || !!config.oneroster_client_secret,
            });
          });
        }
      }
    }).catch(function() {
      setSaving(false);
      setError("Failed to save");
    });
  }

  function handleTestConnection() {
    setTesting(true);
    setTestResult(null);
    api.testDistrictConnection().then(function(res) {
      setTesting(false);
      setTestResult(res);
    }).catch(function() {
      setTesting(false);
      setTestResult({ error: "Connection failed" });
    });
  }

  function handleSaveKeys() {
    setSaving(true);
    setError("");
    setKeysSaved(false);
    var payload = { ai_keys: true };
    if (config.openai_api_key) payload.openai_api_key = config.openai_api_key;
    if (config.anthropic_api_key) payload.anthropic_api_key = config.anthropic_api_key;
    if (config.gemini_api_key) payload.gemini_api_key = config.gemini_api_key;
    api.saveDistrictConfig(payload).then(function(res) {
      setSaving(false);
      if (res && res.error) {
        setError(res.error);
      } else {
        setKeysSaved(true);
        setHasKeys(function(prev) {
          return Object.assign({}, prev, {
            has_openai: prev.has_openai || !!config.openai_api_key,
            has_anthropic: prev.has_anthropic || !!config.anthropic_api_key,
            has_gemini: prev.has_gemini || !!config.gemini_api_key,
          });
        });
      }
    }).catch(function() {
      setSaving(false);
      setError("Failed to save keys");
    });
  }

  function handleChangePassword() {
    setPwMsg("");
    setPwErr("");
    if (newPw.length < 8) {
      setPwErr("New password must be at least 8 characters");
      return;
    }
    api.changeDistrictPassword(currentPw, newPw).then(function(res) {
      if (res && res.error) {
        setPwErr(res.error);
      } else {
        setPwMsg("Password changed successfully");
        setCurrentPw("");
        setNewPw("");
      }
    }).catch(function() {
      setPwErr("Failed to change password");
    });
  }

  function handleLogout() {
    api.districtLogout().then(function() {
      onLogout();
    });
  }

  function applyPreset(preset) {
    if (preset === "classlink") {
      updateField("oneroster_token_url", config.oneroster_base_url.replace(/\/ims\/oneroster\/.*/, "") + "/oauth/token");
    } else if (preset === "powerschool") {
      updateField("oneroster_token_url", config.oneroster_base_url.replace(/\/ws\/.*/, "") + "/oauth/access_token");
    }
  }

  return {
    updateField: updateField,
    toggleSecret: toggleSecret,
    handleSaveSIS: handleSaveSIS,
    handleTestConnection: handleTestConnection,
    handleSaveKeys: handleSaveKeys,
    handleChangePassword: handleChangePassword,
    handleLogout: handleLogout,
    applyPreset: applyPreset,
  };
}
