import { useState, useEffect } from "react";
import Icon from "./Icon";
import { getAuthHeaders } from "../services/api";
import { RUBRIC_PRESETS, getPresetForStateSubject } from "../data/rubricPresets";
import { STEPS } from "./onboarding-wizard/constants";
import WelcomeStep from "./onboarding-wizard/WelcomeStep";
import AboutYouStep from "./onboarding-wizard/AboutYouStep";
import ClassroomStep from "./onboarding-wizard/ClassroomStep";
import GradingStyleStep from "./onboarding-wizard/GradingStyleStep";
import RubricSetupStep from "./onboarding-wizard/RubricSetupStep";
import AiConnectionStep from "./onboarding-wizard/AiConnectionStep";
import RosterStep from "./onboarding-wizard/RosterStep";
import AllSetStep from "./onboarding-wizard/AllSetStep";
import WizardProgressHeader from "./onboarding-wizard/WizardProgressHeader";

// Thin orchestrator (CQ wave 3 split — was a single 1,048-line component).
// ALL wizard state lives here: the step components under onboarding-wizard/
// render conditionally, so any state inside them would reset on navigation.
export default function OnboardingWizard({
  config,
  setConfig,
  rubric,
  setRubric,
  apiKeys,
  setApiKeys,
  onComplete,
  addToast,
  theme,
  toggleTheme,
  user,
}) {
  const [step, setStep] = useState(0);
  const [wizardData, setWizardData] = useState({
    teacher_name: config.teacher_name || "",
    teacher_email: config.teacher_email || "",
    school_name: config.school_name || "",
    grade_level: config.grade_level || "7",
    subject: config.subject || "US History",
    state: config.state || "FL",
    grading_period: config.grading_period || "Q1",
    gradingStyle: rubric.gradingStyle || "lenient",
    openai_key: "",
    anthropic_key: "",
    gemini_key: "",
  });
  const [showExtraKeys, setShowExtraKeys] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);
  const [keysSaved, setKeysSaved] = useState(false);
  // "preset" = use matched B.E.S.T./standard preset, "standard" = use standard, "custom" = skip (customize later)
  const [rubricChoice, setRubricChoice] = useState("preset");

  // Detect SSO login from user prop (reliable) or window fallback.
  // auth_source is the canonical signal (UUID-id ClassLink teachers won't have
  // a 'classlink:' prefix); id-prefix is kept as fallback for legacy sessions.
  var _userId = (user && user.id) || (window.__graiderUser && window.__graiderUser.id) || '';
  var _gu = (typeof window !== 'undefined' && window.__graiderUser) || {};
  var _authSource = (user && user.auth_source) || _gu.auth_source || '';
  const isCleverUser = _authSource === 'clever' || _userId.startsWith('clever:');
  const isClassLinkUser = _authSource === 'classlink' || _userId.startsWith('classlink:');
  const isSSOUser = isCleverUser || isClassLinkUser;

  // Pre-populate from existing config and Clever session on mount
  useEffect(() => {
    var cleverUser = window.__graiderUser || {};
    var cleverName = cleverUser.name || "";
    var cleverEmail = cleverUser.email || "";
    setWizardData((prev) => ({
      ...prev,
      teacher_name: config.teacher_name || cleverName || prev.teacher_name,
      teacher_email: config.teacher_email || cleverEmail || prev.teacher_email,
      school_name: config.school_name || prev.school_name,
      grade_level: config.grade_level || prev.grade_level,
      subject: config.subject || prev.subject,
      state: config.state || prev.state,
      grading_period: config.grading_period || prev.grading_period,
      gradingStyle: rubric.gradingStyle || prev.gradingStyle,
    }));
  }, []);

  const updateField = (field, value) => {
    setWizardData((prev) => ({ ...prev, [field]: value }));
  };

  const canContinue = () => {
    if (step === 1) return wizardData.teacher_name.trim().length > 0;
    if (step === 6) return true; // Import Roster is informational
    return true;
  };

  const handleSaveApiKeys = async () => {
    const hasAnyKey = wizardData.openai_key || wizardData.anthropic_key || wizardData.gemini_key;
    if (!hasAnyKey) return;

    setSavingKeys(true);
    try {
      const authHdrs = await getAuthHeaders();
      const response = await fetch("/api/save-api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHdrs },
        body: JSON.stringify({
          openai_key: wizardData.openai_key || undefined,
          anthropic_key: wizardData.anthropic_key || undefined,
          gemini_key: wizardData.gemini_key || undefined,
        }),
      });
      const data = await response.json();
      if (data.status === "success") {
        setApiKeys((prev) => ({
          ...prev,
          openai: "",
          anthropic: "",
          gemini: "",
          openaiConfigured: data.openai_configured,
          anthropicConfigured: data.anthropic_configured,
          geminiConfigured: data.gemini_configured,
        }));
        setKeysSaved(true);
        addToast("API keys saved successfully", "success");
      } else {
        addToast(data.error || "Failed to save API keys", "error");
      }
    } catch (err) {
      addToast("Failed to save API keys: " + err.message, "error");
    } finally {
      setSavingKeys(false);
    }
  };

  const handleNext = async () => {
    // Save API keys when leaving step 5 (AI Connection)
    if (step === 5) {
      const hasAnyKey = wizardData.openai_key || wizardData.anthropic_key || wizardData.gemini_key;
      if (hasAnyKey && !keysSaved) {
        await handleSaveApiKeys();
      }
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const handleBack = () => {
    setStep((s) => Math.max(s - 1, 0));
  };

  const handleComplete = (navigateTo) => {
    // Push wizard data into config
    var updates = {
      teacher_name: wizardData.teacher_name,
      teacher_email: wizardData.teacher_email,
      school_name: wizardData.school_name,
      grade_level: wizardData.grade_level,
      subject: wizardData.subject,
      state: wizardData.state,
      grading_period: wizardData.grading_period,
      onboarding_completed: true,
    };
    setConfig((prev) => ({ ...prev, ...updates }));

    // Push grading style into rubric, and apply preset categories if selected
    const rubricUpdate = { gradingStyle: wizardData.gradingStyle };
    if (rubricChoice === "preset") {
      const preset = getPresetForStateSubject(wizardData.state, wizardData.subject);
      rubricUpdate.categories = preset.categories.map((c) => ({ ...c }));
    } else if (rubricChoice === "standard") {
      rubricUpdate.categories = RUBRIC_PRESETS.default.categories.map((c) => ({ ...c }));
    }
    // "custom" leaves rubric.categories unchanged

    setRubric((prev) => ({ ...prev, ...rubricUpdate }));

    addToast("Setup complete! Welcome to Graider.", "success");
    onComplete(navigateTo);
  };

  const hasAnyApiKey = apiKeys.openaiConfigured || apiKeys.anthropicConfigured || apiKeys.geminiConfigured || keysSaved;

  // Clever district users may have API keys pre-configured by their district admin
  const nextDisabled = !canContinue() || (step === 5 && !hasAnyApiKey && !isCleverUser);

  const getNextLabel = () => {
    if (step === 0) return "Let's Get Started";
    if (step === STEPS.length - 1) return "Start Using Graider";
    return "Continue";
  };

  // --- Render each step ---

  const renderCurrentStep = () => {
    switch (step) {
      case 0: return <WelcomeStep isCleverUser={isCleverUser} />;
      case 1: return <AboutYouStep wizardData={wizardData} updateField={updateField} isCleverUser={isCleverUser} />;
      case 2: return <ClassroomStep wizardData={wizardData} updateField={updateField} />;
      case 3: return <GradingStyleStep wizardData={wizardData} updateField={updateField} />;
      case 4: return <RubricSetupStep wizardData={wizardData} rubricChoice={rubricChoice} setRubricChoice={setRubricChoice} />;
      case 5: return (
        <AiConnectionStep
          wizardData={wizardData}
          updateField={updateField}
          apiKeys={apiKeys}
          isCleverUser={isCleverUser}
          hasAnyApiKey={hasAnyApiKey}
          showExtraKeys={showExtraKeys}
          setShowExtraKeys={setShowExtraKeys}
          savingKeys={savingKeys}
        />
      );
      case 6: return <RosterStep isSSOUser={isSSOUser} isCleverUser={isCleverUser} />;
      case 7: return (
        <AllSetStep
          wizardData={wizardData}
          rubricChoice={rubricChoice}
          hasAnyApiKey={hasAnyApiKey}
          isSSOUser={isSSOUser}
          isCleverUser={isCleverUser}
          handleComplete={handleComplete}
        />
      );
      default: return null;
    }
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "var(--modal-bg)",
      zIndex: 2000,
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20,
    }}>
      <div style={{
        background: "var(--modal-content-bg)",
        borderRadius: 20,
        border: "1px solid var(--glass-border)",
        width: "100%", maxWidth: 600,
        maxHeight: "90vh",
        display: "flex", flexDirection: "column",
        overflow: "hidden",
      }}>
        <WizardProgressHeader step={step} theme={theme} toggleTheme={toggleTheme} />

        {/* Content */}
        <div style={{
          flex: 1, overflow: "auto",
          padding: "8px 24px 24px",
        }}>
          {renderCurrentStep()}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "16px 24px",
          borderTop: "1px solid var(--glass-border)",
        }}>
          <div>
            {step > 0 && (
              <button
                onClick={handleBack}
                className="btn btn-secondary"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="ChevronLeft" size={16} />
                Back
              </button>
            )}
          </div>
          <button
            onClick={step === STEPS.length - 1 ? () => handleComplete() : handleNext}
            disabled={!canContinue()}
            className="btn btn-primary"
            style={{
              display: "flex", alignItems: "center", gap: 6,
              opacity: canContinue() ? 1 : 0.5,
              cursor: canContinue() ? "pointer" : "not-allowed",
            }}
          >
            {getNextLabel()}
            {step < STEPS.length - 1 && <Icon name="ChevronRight" size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
