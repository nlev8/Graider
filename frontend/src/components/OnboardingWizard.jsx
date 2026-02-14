import { useState, useEffect } from "react";
import Icon from "./Icon";
import { getAuthHeaders } from "../services/api";
import { RUBRIC_PRESETS, getPresetForStateSubject } from "../data/rubricPresets";

const STEPS = [
  { title: "Welcome to Graider!", icon: "GraduationCap" },
  { title: "About You", icon: "User" },
  { title: "Your Classroom", icon: "School" },
  { title: "Grading Style", icon: "ClipboardCheck" },
  { title: "Rubric Setup", icon: "ClipboardList" },
  { title: "AI Connection", icon: "Cpu" },
  { title: "All Set!", icon: "PartyPopper" },
];

const GRADE_LEVELS = [
  "K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
];

const SUBJECTS = [
  "US History", "World History", "English Language Arts", "Mathematics",
  "Science", "Biology", "Chemistry", "Physics", "Social Studies",
  "Government", "Economics", "Geography", "Spanish", "French",
  "Art", "Music", "Physical Education", "Health", "Computer Science",
];

const STATES = [
  { value: "FL", label: "Florida" },
  { value: "TX", label: "Texas" },
  { value: "CA", label: "California" },
  { value: "NY", label: "New York" },
  { value: "IL", label: "Illinois" },
  { value: "PA", label: "Pennsylvania" },
  { value: "OH", label: "Ohio" },
  { value: "GA", label: "Georgia" },
  { value: "NC", label: "North Carolina" },
  { value: "MI", label: "Michigan" },
  { value: "NJ", label: "New Jersey" },
  { value: "VA", label: "Virginia" },
  { value: "WA", label: "Washington" },
  { value: "AZ", label: "Arizona" },
  { value: "MA", label: "Massachusetts" },
  { value: "TN", label: "Tennessee" },
  { value: "IN", label: "Indiana" },
  { value: "MO", label: "Missouri" },
  { value: "MD", label: "Maryland" },
  { value: "WI", label: "Wisconsin" },
  { value: "CO", label: "Colorado" },
  { value: "MN", label: "Minnesota" },
  { value: "SC", label: "South Carolina" },
  { value: "AL", label: "Alabama" },
  { value: "LA", label: "Louisiana" },
  { value: "KY", label: "Kentucky" },
  { value: "OR", label: "Oregon" },
  { value: "OK", label: "Oklahoma" },
  { value: "CT", label: "Connecticut" },
  { value: "UT", label: "Utah" },
  { value: "IA", label: "Iowa" },
  { value: "NV", label: "Nevada" },
  { value: "AR", label: "Arkansas" },
  { value: "MS", label: "Mississippi" },
  { value: "KS", label: "Kansas" },
  { value: "NM", label: "New Mexico" },
  { value: "NE", label: "Nebraska" },
  { value: "ID", label: "Idaho" },
  { value: "WV", label: "West Virginia" },
  { value: "HI", label: "Hawaii" },
  { value: "NH", label: "New Hampshire" },
  { value: "ME", label: "Maine" },
  { value: "MT", label: "Montana" },
  { value: "RI", label: "Rhode Island" },
  { value: "DE", label: "Delaware" },
  { value: "SD", label: "South Dakota" },
  { value: "ND", label: "North Dakota" },
  { value: "AK", label: "Alaska" },
  { value: "VT", label: "Vermont" },
  { value: "WY", label: "Wyoming" },
  { value: "DC", label: "Washington D.C." },
];

const GRADING_PERIODS = [
  { value: "Q1", label: "Quarter 1" },
  { value: "Q2", label: "Quarter 2" },
  { value: "Q3", label: "Quarter 3" },
  { value: "Q4", label: "Quarter 4" },
  { value: "S1", label: "Semester 1" },
  { value: "S2", label: "Semester 2" },
  { value: "FY", label: "Full Year" },
];

const GRADING_STYLES = [
  {
    value: "lenient",
    label: "Lenient",
    icon: "Heart",
    description: "Focus on effort and growth. Best for younger students or building confidence.",
    color: "#22c55e",
  },
  {
    value: "standard",
    label: "Standard",
    icon: "Scale",
    description: "Balanced feedback with fair expectations. Good for most classroom settings.",
    color: "#6366f1",
  },
  {
    value: "strict",
    label: "Strict",
    icon: "Shield",
    description: "High expectations with detailed corrections. Best for advanced or honors classes.",
    color: "#f59e0b",
  },
];

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
  const [skipWarning, setSkipWarning] = useState(false);
  // "preset" = use matched B.E.S.T./standard preset, "standard" = use standard, "custom" = skip (customize later)
  const [rubricChoice, setRubricChoice] = useState("preset");

  // Pre-populate from existing config on mount
  useEffect(() => {
    setWizardData((prev) => ({
      ...prev,
      teacher_name: config.teacher_name || prev.teacher_name,
      teacher_email: config.teacher_email || prev.teacher_email,
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
    setSkipWarning(false);
    setStep((s) => Math.max(s - 1, 0));
  };

  const handleComplete = (navigateTo) => {
    // Push wizard data into config
    setConfig((prev) => ({
      ...prev,
      teacher_name: wizardData.teacher_name,
      teacher_email: wizardData.teacher_email,
      school_name: wizardData.school_name,
      grade_level: wizardData.grade_level,
      subject: wizardData.subject,
      state: wizardData.state,
      grading_period: wizardData.grading_period,
      onboarding_completed: true,
    }));

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

  const nextDisabled = !canContinue() || (step === 5 && !hasAnyApiKey && !skipWarning);

  const getNextLabel = () => {
    if (step === 0) return "Let's Get Started";
    if (step === STEPS.length - 1) return "Start Using Graider";
    if (step === 5 && !hasAnyApiKey && !skipWarning) return "Continue";
    return "Continue";
  };

  // --- Render each step ---

  const renderStep0 = () => (
    <div style={{ textAlign: "center", padding: "20px 0" }}>
      <div style={{
        width: 80, height: 80, borderRadius: "50%",
        background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 24px",
      }}>
        <Icon name="GraduationCap" size={40} style={{ color: "#fff" }} />
      </div>
      <h2 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: 12 }}>
        Welcome to Graider!
      </h2>
      <p style={{ fontSize: "1.05rem", color: "var(--text-secondary)", lineHeight: 1.6, maxWidth: 420, margin: "0 auto" }}>
        Your AI-powered grading assistant. Let's get you set up in just a few quick steps so Graider can work best for your classroom.
      </p>
    </div>
  );

  const renderStep1 = () => (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>About You</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Tell us a little about yourself so we can personalize your experience.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Teacher Name *</label>
          <input
            className="input"
            placeholder="e.g. Ms. Johnson"
            value={wizardData.teacher_name}
            onChange={(e) => updateField("teacher_name", e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Email Address</label>
          <input
            className="input"
            type="email"
            placeholder="e.g. johnson@school.edu"
            value={wizardData.teacher_email}
            onChange={(e) => updateField("teacher_email", e.target.value)}
          />
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>School Name</label>
          <input
            className="input"
            placeholder="e.g. Lincoln Middle School"
            value={wizardData.school_name}
            onChange={(e) => updateField("school_name", e.target.value)}
          />
        </div>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Your Classroom</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        This helps Graider set age-appropriate expectations and align with your state standards.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Grade Level</label>
          <select
            className="input"
            value={wizardData.grade_level}
            onChange={(e) => updateField("grade_level", e.target.value)}
          >
            {GRADE_LEVELS.map((g) => (
              <option key={g} value={g}>{g === "K" ? "Kindergarten" : "Grade " + g}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Subject</label>
          <select
            className="input"
            value={wizardData.subject}
            onChange={(e) => updateField("subject", e.target.value)}
          >
            {SUBJECTS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>State</label>
          <select
            className="input"
            value={wizardData.state}
            onChange={(e) => updateField("state", e.target.value)}
          >
            {STATES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Grading Period</label>
          <select
            className="input"
            value={wizardData.grading_period}
            onChange={(e) => updateField("grading_period", e.target.value)}
          >
            {GRADING_PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Grading Style</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Choose how Graider approaches grading. You can change this anytime in Settings.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {GRADING_STYLES.map((style) => {
          const isSelected = wizardData.gradingStyle === style.value;
          return (
            <button
              key={style.value}
              onClick={() => updateField("gradingStyle", style.value)}
              style={{
                display: "flex", alignItems: "center", gap: 16,
                padding: "16px 20px",
                background: isSelected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
                border: isSelected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                borderRadius: 12, cursor: "pointer",
                textAlign: "left", transition: "all 0.2s",
                color: "var(--text-primary)", fontFamily: "inherit",
              }}
            >
              <div style={{
                width: 44, height: 44, borderRadius: 10,
                background: isSelected ? style.color + "22" : "var(--glass-bg)",
                border: "1px solid " + (isSelected ? style.color : "var(--glass-border)"),
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
              }}>
                <Icon name={style.icon} size={22} style={{ color: isSelected ? style.color : "var(--text-secondary)" }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "1rem", marginBottom: 2 }}>
                  {style.label}
                  {isSelected && (
                    <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: 8 }} />
                  )}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                  {style.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderStep4 = () => {
    const isFL = wizardData.state === "FL";
    const matchedPreset = getPresetForStateSubject(wizardData.state, wizardData.subject);
    const standardPreset = RUBRIC_PRESETS.default;

    const renderPresetCard = (preset, selected, onClick) => (
      <button
        onClick={onClick}
        style={{
          display: "block", width: "100%", textAlign: "left",
          padding: "16px",
          background: selected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
          border: selected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
          borderRadius: 12, cursor: "pointer",
          transition: "all 0.2s",
          color: "var(--text-primary)", fontFamily: "inherit",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <span style={{ fontWeight: 600, fontSize: "1rem" }}>{preset.name}</span>
          {preset.badge && (
            <span style={{
              padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
              background: "rgba(99,102,241,0.2)", color: "#818cf8",
            }}>
              {preset.badge}
            </span>
          )}
          {selected && <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: "auto" }} />}
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 10 }}>
          {preset.description}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {preset.categories.map((cat) => (
            <span key={cat.name} style={{
              padding: "4px 10px", borderRadius: 6, fontSize: "0.75rem",
              background: "var(--input-bg)", color: "var(--text-secondary)",
            }}>
              {cat.name} {cat.weight}%
            </span>
          ))}
        </div>
      </button>
    );

    return (
      <div style={{ padding: "10px 0" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Rubric Setup</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.95rem" }}>
          {isFL
            ? "We matched a B.E.S.T.-aligned rubric for your subject. You can customize it later in Settings."
            : "Choose a starting rubric for grading. You can customize it later in Settings."}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Show B.E.S.T. preset for FL if different from standard */}
          {isFL && matchedPreset.badge && (
            renderPresetCard(
              matchedPreset,
              rubricChoice === "preset",
              () => setRubricChoice("preset")
            )
          )}

          {/* Standard rubric option */}
          {renderPresetCard(
            standardPreset,
            isFL ? rubricChoice === "standard" : rubricChoice === "preset",
            () => setRubricChoice(isFL ? "standard" : "preset")
          )}

          {/* Customize later */}
          <button
            onClick={() => setRubricChoice("custom")}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "12px 16px",
              background: rubricChoice === "custom" ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
              border: rubricChoice === "custom" ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
              borderRadius: 12, cursor: "pointer",
              transition: "all 0.2s", textAlign: "left",
              color: "var(--text-primary)", fontFamily: "inherit",
            }}
          >
            <Icon name="Settings" size={18} style={{ color: "var(--text-secondary)" }} />
            <div>
              <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Customize Later</span>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                Keep your current rubric and adjust in Settings
              </p>
            </div>
            {rubricChoice === "custom" && <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: "auto" }} />}
          </button>
        </div>
      </div>
    );
  };

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

  const renderStep5 = () => (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>AI Connection</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Graider needs at least one AI provider to grade assignments. OpenAI is recommended.
      </p>

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
          {renderKeyInput(
            "Google Gemini API Key",
            "gemini_key",
            apiKeys.geminiConfigured,
            "https://aistudio.google.com/apikey",
            "aistudio.google.com"
          )}
        </>
      )}

      {!hasAnyApiKey && !skipWarning && (
        <div style={{
          marginTop: 16, padding: "12px 16px",
          background: "rgba(245,158,11,0.1)",
          border: "1px solid rgba(245,158,11,0.3)",
          borderRadius: 8, fontSize: "0.85rem",
          color: "var(--text-secondary)",
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <Icon name="AlertTriangle" size={18} style={{ color: "#f59e0b", flexShrink: 0, marginTop: 1 }} />
          <div>
            No API key configured yet. You'll need one to grade assignments.{" "}
            <button
              onClick={() => setSkipWarning(true)}
              style={{
                background: "none", border: "none", cursor: "pointer",
                color: "var(--accent-primary)", textDecoration: "underline",
                padding: 0, fontSize: "0.85rem",
              }}
            >
              Skip for now
            </button>
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

  const renderStep6 = () => {
    const selectedPreset = rubricChoice === "preset"
      ? getPresetForStateSubject(wizardData.state, wizardData.subject)
      : rubricChoice === "standard"
        ? RUBRIC_PRESETS.default
        : null;

    const summaryItems = [
      { icon: "User", label: "Teacher", value: wizardData.teacher_name },
      { icon: "School", label: "School", value: wizardData.school_name || "Not set" },
      { icon: "BookOpen", label: "Subject", value: "Grade " + wizardData.grade_level + " " + wizardData.subject },
      { icon: "MapPin", label: "State", value: STATES.find((s) => s.value === wizardData.state)?.label || wizardData.state },
      { icon: "Calendar", label: "Period", value: GRADING_PERIODS.find((p) => p.value === wizardData.grading_period)?.label || wizardData.grading_period },
      { icon: "ClipboardCheck", label: "Style", value: GRADING_STYLES.find((s) => s.value === wizardData.gradingStyle)?.label || wizardData.gradingStyle },
      { icon: "ClipboardList", label: "Rubric", value: selectedPreset ? selectedPreset.name : "Custom (unchanged)" },
      { icon: "Cpu", label: "AI Provider", value: hasAnyApiKey ? "Connected" : "Not configured" },
    ];

    return (
      <div style={{ textAlign: "center", padding: "10px 0" }}>
        <div style={{
          width: 64, height: 64, borderRadius: "50%",
          background: "linear-gradient(135deg, #22c55e, #16a34a)",
          display: "flex", alignItems: "center", justifyContent: "center",
          margin: "0 auto 20px",
        }}>
          <Icon name="Check" size={32} style={{ color: "#fff" }} />
        </div>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>You're All Set!</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
          Here's a summary of your setup. You can change any of these in Settings.
        </p>
        <div style={{
          background: "var(--glass-bg)",
          border: "1px solid var(--glass-border)",
          borderRadius: 12, padding: 16,
          textAlign: "left", marginBottom: 16,
        }}>
          {summaryItems.map((item, i) => (
            <div
              key={i}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "10px 0",
                borderBottom: i < summaryItems.length - 1 ? "1px solid var(--glass-border)" : "none",
              }}
            >
              <Icon name={item.icon} size={18} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", width: 80, flexShrink: 0 }}>
                {item.label}
              </span>
              <span style={{ fontSize: "0.95rem", fontWeight: 500 }}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
        <button
          onClick={() => handleComplete("builder")}
          className="btn btn-secondary"
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 20px", fontSize: "0.95rem",
          }}
        >
          <Icon name="Plus" size={18} />
          Create Your First Assignment
        </button>
      </div>
    );
  };

  const renderCurrentStep = () => {
    switch (step) {
      case 0: return renderStep0();
      case 1: return renderStep1();
      case 2: return renderStep2();
      case 3: return renderStep3();
      case 4: return renderStep4();
      case 5: return renderStep5();
      case 6: return renderStep6();
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
        {/* Progress bar + theme toggle */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "20px 24px 0",
        }}>
          <div style={{ display: "flex", gap: 4, flex: 1 }}>
            {STEPS.map((_, i) => (
              <div
                key={i}
                style={{
                  flex: 1, height: 4, borderRadius: 2,
                  background: i <= step ? "var(--accent-primary)" : "var(--glass-border)",
                  transition: "background 0.3s",
                }}
              />
            ))}
          </div>
          {toggleTheme && (
            <button
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              style={{
                width: 32, height: 32, borderRadius: 8,
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, transition: "all 0.2s",
                color: "var(--text-primary)", padding: 0,
              }}
            >
              <Icon name={theme === "dark" ? "Sun" : "Moon"} size={16} />
            </button>
          )}
        </div>

        {/* Step indicator */}
        <div style={{
          padding: "12px 24px 0",
          fontSize: "0.75rem",
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}>
          Step {step + 1} of {STEPS.length}
        </div>

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
