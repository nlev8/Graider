import React, { useRef, useState } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";
import { getAuthHeaders } from "../services/api";
import { RUBRIC_PRESETS } from "../data/rubricPresets";
import OnboardingWizard from "../components/OnboardingWizard";

export default function SettingsTab({
  settingsTab,
  setSettingsTab,
  config,
  setConfig,
  rubric,
  setRubric,
  globalAINotes,
  setGlobalAINotes,
  apiKeys,
  setApiKeys,
  showApiKeys,
  setShowApiKeys,
  savingApiKeys,
  setSavingApiKeys,
  costSummary,
  setCostSummary,
  subscription,
  setSubscription,
  subscriptionLoading,
  setSubscriptionLoading,
  periods,
  setPeriods,
  rosters,
  setRosters,
  expandedPeriod,
  setExpandedPeriod,
  expandedStudents,
  setExpandedStudents,
  loadingExpandedStudents,
  setLoadingExpandedStudents,
  newPeriodName,
  setNewPeriodName,
  uploadingPeriod,
  setUploadingPeriod,
  newStudent,
  setNewStudent,
  addingStudent,
  setAddingStudent,
  editingStudentId,
  setEditingStudentId,
  editStudentData,
  setEditStudentData,
  studentAccommodations,
  setStudentAccommodations,
  selectedAccommodationPresets,
  setSelectedAccommodationPresets,
  accommodationCustomNotes,
  setAccommodationCustomNotes,
  accommodationModal,
  setAccommodationModal,
  accommEllLanguage,
  setAccommEllLanguage,
  accommSelectedStudents,
  setAccommSelectedStudents,
  accommPeriodFilter,
  setAccommPeriodFilter,
  accommStudentsList,
  setAccommStudentsList,
  studentHistoryList,
  setStudentHistoryList,
  studentHistoryLoading,
  setStudentHistoryLoading,
  selectedStudentHistory,
  setSelectedStudentHistory,
  vportalEmail,
  setVportalEmail,
  vportalPassword,
  setVportalPassword,
  vportalSaving,
  setVportalSaving,
  vportalConfigured,
  setVportalConfigured,
  syncingCloud,
  setSyncingCloud,
  parentContacts,
  setParentContacts,
  parentContactMapping,
  setParentContactMapping,
  uploadingParentContacts,
  setUploadingParentContacts,
  customTools,
  setCustomTools,
  newCustomTool,
  setNewCustomTool,
  supportDocs,
  setSupportDocs,
  uploadingDoc,
  setUploadingDoc,
  newDocType,
  setNewDocType,
  newDocDescription,
  setNewDocDescription,
  assessmentTemplates,
  setAssessmentTemplates,
  uploadingTemplate,
  setUploadingTemplate,
  addStudentModal,
  setAddStudentModal,
  rosterMappingModal,
  setRosterMappingModal,
  focusImporting,
  setFocusImporting,
  focusImportProgress,
  setFocusImportProgress,
  importStudentData,
  setImportStudentData,
  exportStudentSearch,
  setExportStudentSearch,
  showOnboardingWizard,
  setShowOnboardingWizard,
  loadAvailableFiles,
  filesLoading,
  sortedPeriods,
  accommodationPresets,
  handleBrowse,
  EDTECH_TOOLS,
  MODEL_COST_PER_ASSIGNMENT,
  addToast,
}) {
  const periodInputRef = useRef(null);
  const parentContactsInputRef = useRef(null);
  const supportDocInputRef = useRef(null);
  const importFileRef = useRef(null);
  const [showVportalPassword, setShowVportalPassword] = useState(false);

  return (
    <>
        <div className="fade-in glass-card" style={{ padding: "25px" }}>
          <h2
            style={{
              fontSize: "1.3rem",
              fontWeight: 700,
              marginBottom: "15px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <Icon name="Settings" size={24} />
            Settings
          </h2>

          {/* Settings Sub-tabs */}
          <div style={{ display: "flex", gap: "4px", marginBottom: "20px", borderBottom: "1px solid var(--glass-border)", paddingBottom: "12px", flexWrap: "wrap" }}>
            {[
              { id: "general", label: "General", icon: "FolderOpen" },
              { id: "grading", label: "Grading", icon: "ClipboardCheck" },
              { id: "ai", label: "AI", icon: "Sparkles" },
              { id: "classroom", label: "Classroom", icon: "Users" },
              { id: "integration", label: "Tools", icon: "Laptop" },
              { id: "privacy", label: "Privacy", icon: "Shield" },
              { id: "billing", label: "Billing", icon: "CreditCard" },
              { id: "resources", label: "Resources", icon: "FolderOpen" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSettingsTab(tab.id)}
                style={{
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "none",
                  background: settingsTab === tab.id ? "var(--accent-primary)" : "transparent",
                  color: settingsTab === tab.id ? "white" : "var(--text-secondary)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "0.85rem",
                  fontWeight: settingsTab === tab.id ? 600 : 500,
                  transition: "all 0.2s",
                }}
              >
                <Icon name={tab.icon} size={16} />
                {tab.label}
              </button>
            ))}
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            {/* General Tab */}
            {settingsTab === "general" && (
              <div data-tutorial="settings-general">
            <div>
              <label className="label">Assignments Folder</label>
              <div style={{ display: "flex", gap: "10px" }}>
                <input
                  type="text"
                  className="input"
                  value={config.assignments_folder}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      assignments_folder: e.target.value,
                    }))
                  }
                />
                <button
                  onClick={() =>
                    handleBrowse("folder", "assignments_folder")
                  }
                  className="btn btn-secondary"
                >
                  Browse
                </button>
                <button
                  onClick={loadAvailableFiles}
                  disabled={!config.assignments_folder || filesLoading}
                  className="btn btn-secondary"
                  style={{
                    opacity: !config.assignments_folder ? 0.5 : 1,
                  }}
                >
                  {filesLoading ? "Loading..." : "Load Files"}
                </button>
              </div>
            </div>

            <div>
              <label className="label">Output Folder</label>
              <div style={{ display: "flex", gap: "10px" }}>
                <input
                  type="text"
                  className="input"
                  value={config.output_folder}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      output_folder: e.target.value,
                    }))
                  }
                />
                <button
                  onClick={() =>
                    handleBrowse("folder", "output_folder")
                  }
                  className="btn btn-secondary"
                >
                  Browse
                </button>
              </div>
            </div>

            {/* Teacher & School Info */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: "20px",
              }}
            >
              <div>
                <label className="label">Teacher Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.teacher_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_name: e.target.value,
                    }))
                  }
                  placeholder="Mr. Smith"
                />
              </div>
              <div>
                <label className="label">Teacher Email</label>
                <input
                  type="email"
                  className="input"
                  value={config.teacher_email}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_email: e.target.value,
                    }))
                  }
                  placeholder="teacher@school.edu"
                />
                <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                  Students will reply to this email
                </span>
              </div>
              <div>
                <label className="label">School Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.school_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      school_name: e.target.value,
                    }))
                  }
                  placeholder="Lincoln Middle School"
                />
              </div>
            </div>

            {/* Email Signature */}
            <div>
              <label className="label">Email Signature</label>
              <textarea
                className="input"
                value={config.email_signature}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    email_signature: e.target.value,
                  }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.stopPropagation();
                  }
                }}
                placeholder={"Best regards," + String.fromCharCode(10) + "Mr. Smith" + String.fromCharCode(10) + "Room 204 | Office Hours: Mon-Fri 3-4pm"}
                rows={4}
                style={{ resize: "vertical", minHeight: "100px", fontFamily: "inherit", lineHeight: "1.5" }}
              />
              <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                Appears at the end of grade feedback emails
              </span>
            </div>

            {/* Notifications */}
            <div style={{ marginTop: "30px" }}>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="Bell" size={20} style={{ color: "#f59e0b" }} />
                Notifications
              </h3>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  cursor: "pointer",
                  padding: "12px 16px",
                  background: "var(--input-bg)",
                  borderRadius: "12px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <input
                  type="checkbox"
                  checked={config.showToastNotifications}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      showToastNotifications: e.target.checked,
                    }))
                  }
                  style={{
                    width: "18px",
                    height: "18px",
                    accentColor: "var(--accent-primary)",
                    cursor: "pointer",
                  }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    Toast Notifications
                  </div>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    Show popup notifications when assignments are graded
                  </div>
                </div>
              </label>
            </div>

            <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--glass-border)" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Setup Wizard</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 12 }}>
                Re-run the initial setup to update your core settings.
              </p>
              <button
                onClick={() => setShowOnboardingWizard(true)}
                className="btn btn-secondary"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="RefreshCw" size={16} />
                Run Setup Wizard Again
              </button>
            </div>
              </div>
            )}

            {/* Grading Tab */}
            {settingsTab === "grading" && (
              <>
            <div
              data-tutorial="settings-grading"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "20px",
              }}
            >
              <div>
                <label className="label">State</label>
                <select
                  className="input"
                  value={config.state}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      state: e.target.value,
                    }))
                  }
                >
                  <option value="FL">Florida</option>
                  <option value="TX">Texas</option>
                  <option value="CA">California</option>
                  <option value="NY">New York</option>
                  <option value="GA">Georgia</option>
                  <option value="NC">North Carolina</option>
                  <option value="VA">Virginia</option>
                  <option value="OH">Ohio</option>
                  <option value="PA">Pennsylvania</option>
                  <option value="IL">Illinois</option>
                </select>
              </div>

              <div>
                <label className="label">Grade Level</label>
                <select
                  className="input"
                  value={config.grade_level}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      grade_level: e.target.value,
                    }))
                  }
                >
                  <option value="K">Kindergarten</option>
                  <option value="1">1st Grade</option>
                  <option value="2">2nd Grade</option>
                  <option value="3">3rd Grade</option>
                  <option value="4">4th Grade</option>
                  <option value="5">5th Grade</option>
                  <option value="6">6th Grade</option>
                  <option value="7">7th Grade</option>
                  <option value="8">8th Grade</option>
                  <option value="9">9th Grade</option>
                  <option value="10">10th Grade</option>
                  <option value="11">11th Grade</option>
                  <option value="12">12th Grade</option>
                </select>
              </div>

              <div>
                <label className="label">Subject</label>
                <select
                  className="input"
                  value={config.subject}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      subject: e.target.value,
                    }))
                  }
                >
                  <option value="US History">U.S. History</option>
                  <option value="World History">World History</option>
                  <option value="Social Studies">Social Studies</option>
                  <option value="Civics">Civics</option>
                  <option value="Geography">Geography</option>
                  <option value="English/ELA">English/ELA</option>
                  <option value="Math">Math</option>
                  <option value="Science">Science</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="label">Grading Period</label>
                <select
                  className="input"
                  value={config.grading_period}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      grading_period: e.target.value,
                    }))
                  }
                >
                  <option value="Q1">Quarter 1 (Q1)</option>
                  <option value="Q2">Quarter 2 (Q2)</option>
                  <option value="Q3">Quarter 3 (Q3)</option>
                  <option value="Q4">Quarter 4 (Q4)</option>
                  <option value="S1">Semester 1 (S1)</option>
                  <option value="S2">Semester 2 (S2)</option>
                </select>
              </div>
              <div>
                <label className="label">Grading Style</label>
                <select
                  className="input"
                  value={rubric.gradingStyle || 'standard'}
                  onChange={(e) =>
                    setRubric((prev) => ({
                      ...prev,
                      gradingStyle: e.target.value,
                    }))
                  }
                >
                  <option value="lenient">Lenient — Reward effort and attempt</option>
                  <option value="standard">Standard — Balanced grading</option>
                  <option value="strict">Strict — Penalize brevity and weak answers</option>
                </select>
              </div>
            </div>

            {/* Quick Presets */}
            <div style={{ marginBottom: "20px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name="Sparkles" size={20} style={{ color: "#8b5cf6" }} />
                Quick Presets
              </h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {Object.entries(RUBRIC_PRESETS)
                  .filter(([key, preset]) => {
                    if (key === "default") return true;
                    return config.state === "FL" && key.startsWith("FL_");
                  })
                  .map(([key, preset]) => (
                    <button
                      key={key}
                      onClick={() => setRubric((prev) => ({ ...prev, categories: preset.categories.map((c) => ({ ...c })) }))}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.8rem", padding: "6px 14px", display: "flex", alignItems: "center", gap: "6px" }}
                    >
                      {preset.badge && (
                        <span style={{ padding: "1px 6px", borderRadius: 4, fontSize: "0.65rem", fontWeight: 600, background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>
                          {preset.badge}
                        </span>
                      )}
                      {preset.name}
                    </button>
                  ))}
              </div>
            </div>

            {/* Rubric Configuration */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="ClipboardCheck"
                  size={20}
                  style={{ color: "#8b5cf6" }}
                />
                Grading Rubric
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Configure how assignments are scored. Weights must total
                100%.
              </p>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  marginBottom: "15px",
                }}
              >
                {rubric.categories.map((cat, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      gap: "10px",
                      alignItems: "center",
                      padding: "12px",
                      background: "var(--input-bg)",
                      borderRadius: "8px",
                    }}
                  >
                    <input
                      type="text"
                      className="input"
                      value={cat.name}
                      onChange={(e) => {
                        const updated = [...rubric.categories];
                        updated[idx].name = e.target.value;
                        setRubric({ ...rubric, categories: updated });
                      }}
                      style={{ flex: 1 }}
                      placeholder="Category name"
                    />
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                      }}
                    >
                      <input
                        type="number"
                        className="input"
                        value={cat.weight}
                        onChange={(e) => {
                          const updated = [...rubric.categories];
                          updated[idx].weight =
                            parseInt(e.target.value) || 0;
                          setRubric({ ...rubric, categories: updated });
                        }}
                        style={{ width: "70px", textAlign: "center" }}
                        min="0"
                        max="100"
                      />
                      <span style={{ color: "var(--text-secondary)" }}>
                        %
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        const updated = rubric.categories.filter(
                          (_, i) => i !== idx,
                        );
                        setRubric({ ...rubric, categories: updated });
                      }}
                      style={{
                        padding: "6px",
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                      }}
                    >
                      <Icon name="X" size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "15px",
                }}
              >
                <button
                  onClick={() => {
                    setRubric({
                      ...rubric,
                      categories: [
                        ...rubric.categories,
                        { name: "", weight: 0, description: "" },
                      ],
                    });
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: "0.85rem" }}
                >
                  <Icon name="Plus" size={16} />
                  Add Category
                </button>
                <button
                  onClick={() => {
                    setRubric((prev) => ({
                      ...prev,
                      categories: RUBRIC_PRESETS.default.categories.map((c) => ({ ...c })),
                    }));
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: "0.85rem" }}
                >
                  <Icon name="RotateCcw" size={16} />
                  Reset to Default
                </button>
                <span
                  style={{
                    fontSize: "0.85rem",
                    color:
                      rubric.categories.reduce(
                        (sum, c) => sum + c.weight,
                        0,
                      ) === 100
                        ? "#10b981"
                        : "#ef4444",
                  }}
                >
                  Total:{" "}
                  {rubric.categories.reduce(
                    (sum, c) => sum + c.weight,
                    0,
                  )}
                  %
                  {rubric.categories.reduce(
                    (sum, c) => sum + c.weight,
                    0,
                  ) !== 100 && " (must equal 100%)"}
                </span>
              </div>
            </div>
              </>
            )}

            {/* AI Tab */}
            {settingsTab === "ai" && (
              <>
            {/* AI Model Selection */}
            <div data-tutorial="settings-ai">
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Sparkles" size={20} style={{ color: "#8b5cf6" }} />
                AI Model
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                Choose which AI model to use for grading and assessment generation.
              </p>
              <select
                className="input"
                value={config.ai_model}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    ai_model: e.target.value,
                  }))
                }
                style={{ maxWidth: "350px" }}
              >
                <optgroup label="OpenAI">
                  <option value="gpt-4o-mini">
                    GPT-4o Mini (Fast & Cheap)
                  </option>
                  <option value="gpt-4o">
                    GPT-4o (Best Quality)
                  </option>
                </optgroup>
                <optgroup label="Anthropic">
                  <option value="claude-haiku">
                    Claude Haiku (Fast & Cheap)
                  </option>
                  <option value="claude-sonnet">
                    Claude Sonnet (Balanced)
                  </option>
                  <option value="claude-opus">
                    Claude Opus (Most Capable)
                  </option>
                </optgroup>
                <optgroup label="Google">
                  <option value="gemini-flash">
                    Gemini 2.0 Flash (Fast & Cheap)
                  </option>
                  <option value="gemini-pro">
                    Gemini 2.0 Pro (Balanced)
                  </option>
                </optgroup>
              </select>
              <p
                style={{
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                  marginTop: "10px",
                  padding: "10px 14px",
                  background: (() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "rgba(74,222,128,0.1)" : "rgba(245,158,11,0.1)";
                  })(),
                  borderRadius: "8px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon
                  name={(() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "CheckCircle" : "AlertCircle";
                  })()}
                  size={16}
                  style={{ color: (() => {
                    const isConfigured = config.ai_model?.startsWith("claude")
                      ? apiKeys.anthropicConfigured
                      : config.ai_model?.startsWith("gemini")
                        ? apiKeys.geminiConfigured
                        : apiKeys.openaiConfigured;
                    return isConfigured ? "#4ade80" : "#f59e0b";
                  })() }}
                />
                {config.ai_model?.startsWith("claude")
                  ? apiKeys.anthropicConfigured
                    ? "Anthropic API connected"
                    : "Add Anthropic API key below to use Claude"
                  : config.ai_model?.startsWith("gemini")
                    ? apiKeys.geminiConfigured
                      ? "Google AI API connected"
                      : "Add Google AI API key below to use Gemini"
                    : apiKeys.openaiConfigured
                      ? "OpenAI API connected"
                      : "Add OpenAI API key below to use GPT"}
              </p>

              {/* Extraction Mode Toggle - A/B Test */}
              <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                <div style={{ marginBottom: "10px" }}>
                  <span style={{ fontWeight: 600 }}>
                    <Icon name="FileSearch" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    Response Extraction Mode
                  </span>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "structured" ? "rgba(59, 130, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "structured" ? "1px solid rgba(59, 130, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="structured"
                      checked={config.extraction_mode === "structured"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>Structured</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Parse with rules</div>
                    </div>
                  </label>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "ai" ? "rgba(139, 92, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "ai" ? "1px solid rgba(139, 92, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="ai"
                      checked={config.extraction_mode === "ai"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>AI-Powered</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Let AI identify responses</div>
                    </div>
                  </label>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "10px" }}>
                  {config.extraction_mode === "structured"
                    ? "Uses parsing rules to separate questions from answers. More predictable but may miss edge cases."
                    : "Sends raw content to AI and lets it identify what's a prompt vs student response. More flexible."}
                </p>
              </div>

              {/* Ensemble Grading Toggle */}
              <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={config.ensemble_enabled}
                    onChange={(e) => setConfig((prev) => ({ ...prev, ensemble_enabled: e.target.checked }))}
                    style={{ width: "18px", height: "18px" }}
                  />
                  <span style={{ fontWeight: 600 }}>
                    <Icon name="Users" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    Ensemble Grading
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    (Grade with multiple AIs for accuracy)
                  </span>
                </label>

                {config.ensemble_enabled && (
                  <div style={{ marginTop: "15px" }}>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      Select 2-3 models to grade each assignment. Final score = median of all models.
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {[
                        { value: "gpt-4o-mini", label: "GPT-4o Mini", cost: "$0.001", provider: "openai" },
                        { value: "gpt-4o", label: "GPT-4o", cost: "$0.015", provider: "openai" },
                        { value: "claude-haiku", label: "Claude Haiku", cost: "$0.002", provider: "anthropic" },
                        { value: "claude-sonnet", label: "Claude Sonnet", cost: "$0.02", provider: "anthropic" },
                        { value: "gemini-flash", label: "Gemini Flash", cost: "$0.0005", provider: "gemini" },
                        { value: "gemini-pro", label: "Gemini Pro", cost: "$0.008", provider: "gemini" },
                      ].map((model) => {
                        const isConfigured = model.provider === "openai" ? apiKeys.openaiConfigured
                          : model.provider === "anthropic" ? apiKeys.anthropicConfigured
                          : apiKeys.geminiConfigured;
                        const isSelected = config.ensemble_models?.includes(model.value);
                        return (
                          <label
                            key={model.value}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              padding: "8px 12px",
                              borderRadius: "8px",
                              background: isSelected ? "rgba(139, 92, 246, 0.15)" : "transparent",
                              border: isSelected ? "1px solid rgba(139, 92, 246, 0.3)" : "1px solid transparent",
                              cursor: isConfigured ? "pointer" : "not-allowed",
                              opacity: isConfigured ? 1 : 0.5,
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              disabled={!isConfigured}
                              onChange={(e) => {
                                setConfig((prev) => {
                                  const models = prev.ensemble_models || [];
                                  if (e.target.checked) {
                                    return { ...prev, ensemble_models: [...models, model.value] };
                                  } else {
                                    return { ...prev, ensemble_models: models.filter((m) => m !== model.value) };
                                  }
                                });
                              }}
                              style={{ width: "16px", height: "16px" }}
                            />
                            <span style={{ flex: 1 }}>{model.label}</span>
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>~{model.cost}/assignment</span>
                            {!isConfigured && (
                              <span style={{ fontSize: "0.7rem", color: "#f59e0b" }}>No API key</span>
                            )}
                          </label>
                        );
                      })}
                    </div>
                    {config.ensemble_models?.length >= 2 && (
                      <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#4ade80" }}>
                        <Icon name="CheckCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                        {config.ensemble_models.length} models selected - estimated ~${(
                          config.ensemble_models.reduce((sum, m) => {
                            return sum + (MODEL_COST_PER_ASSIGNMENT[m] || 0);
                          }, 0)
                        ).toFixed(4)}/assignment
                      </p>
                    )}
                    {config.ensemble_models?.length === 1 && (
                      <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#f59e0b" }}>
                        <Icon name="AlertCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                        Select at least 2 models for ensemble grading
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Global AI Instructions */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="MessageSquare" size={20} style={{ color: "#6366f1" }} />
                Global AI Instructions
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                These instructions apply to both grading AND assessment generation. Include differentiation rules for periods here.
              </p>
              <textarea
                className="input"
                value={globalAINotes}
                onChange={(e) => setGlobalAINotes(e.target.value)}
                placeholder="Example: For assessment generation, Periods 1,2,5 are advanced (7th-8th grade level). Periods 4,6,7 should be 6th grade level only."
                style={{ minHeight: "120px", resize: "vertical" }}
              />
            </div>

            {/* API Keys Section */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="Key" size={20} style={{ color: "#f59e0b" }} />
                API Keys
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Connect your AI provider API keys. Keys are stored
                securely and never shared.
              </p>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "15px",
                }}
              >
                {/* OpenAI API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    OpenAI API Key
                    {apiKeys.openaiConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={showApiKeys.openai ? "text" : "password"}
                        className="input"
                        value={apiKeys.openai}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            openai: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.openaiConfigured
                            ? "••••••••••••••••"
                            : "sk-..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            openai: !prev.openai,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={showApiKeys.openai ? "EyeOff" : "Eye"}
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://platform.openai.com/api-keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      platform.openai.com
                    </a>
                  </p>
                </div>

                {/* Anthropic API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    Anthropic (Claude) API Key
                    {apiKeys.anthropicConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={
                          showApiKeys.anthropic ? "text" : "password"
                        }
                        className="input"
                        value={apiKeys.anthropic}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            anthropic: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.anthropicConfigured
                            ? "••••••••••••••••"
                            : "sk-ant-..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            anthropic: !prev.anthropic,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={
                            showApiKeys.anthropic ? "EyeOff" : "Eye"
                          }
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://console.anthropic.com/settings/keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      console.anthropic.com
                    </a>
                  </p>
                </div>

                {/* Google AI (Gemini) API Key */}
                <div>
                  <label
                    className="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    Google AI (Gemini) API Key
                    {apiKeys.geminiConfigured && (
                      <span
                        style={{
                          color: "#22c55e",
                          fontSize: "0.75rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <Icon name="CheckCircle" size={14} /> Connected
                      </span>
                    )}
                  </label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type={
                          showApiKeys.gemini ? "text" : "password"
                        }
                        className="input"
                        value={apiKeys.gemini}
                        onChange={(e) =>
                          setApiKeys((prev) => ({
                            ...prev,
                            gemini: e.target.value,
                          }))
                        }
                        placeholder={
                          apiKeys.geminiConfigured
                            ? "••••••••••••••••"
                            : "AIza..."
                        }
                        style={{ paddingRight: "40px" }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowApiKeys((prev) => ({
                            ...prev,
                            gemini: !prev.gemini,
                          }))
                        }
                        style={{
                          position: "absolute",
                          right: "10px",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon
                          name={
                            showApiKeys.gemini ? "EyeOff" : "Eye"
                          }
                          size={18}
                        />
                      </button>
                    </div>
                  </div>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginTop: "4px",
                    }}
                  >
                    Get your key from{" "}
                    <a
                      href="https://aistudio.google.com/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      aistudio.google.com
                    </a>
                  </p>
                </div>

                <button
                  onClick={async () => {
                    setSavingApiKeys(true);
                    try {
                      const authHdrs = await getAuthHeaders();
                      const response = await fetch(
                        "/api/save-api-keys",
                        {
                          method: "POST",
                          headers: {
                            "Content-Type": "application/json",
                            ...authHdrs,
                          },
                          body: JSON.stringify({
                            openai_key: apiKeys.openai || undefined,
                            anthropic_key: apiKeys.anthropic || undefined,
                            gemini_key: apiKeys.gemini || undefined,
                          }),
                        },
                      );
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
                        addToast(
                          "API keys saved successfully",
                          "success",
                        );
                      } else {
                        addToast(
                          data.error || "Failed to save API keys",
                          "error",
                        );
                      }
                    } catch (err) {
                      addToast(
                        "Error saving API keys: " + err.message,
                        "error",
                      );
                    } finally {
                      setSavingApiKeys(false);
                    }
                  }}
                  disabled={
                    savingApiKeys ||
                    (!apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini)
                  }
                  className="btn btn-primary"
                  style={{
                    alignSelf: "flex-start",
                    opacity:
                      !apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini ? 0.5 : 1,
                  }}
                >
                  {savingApiKeys ? "Saving..." : "Save API Keys"}
                </button>
              </div>
            </div>

            {/* Assistant Model Selection */}
            <div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                marginBottom: "15px",
                marginTop: "25px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}>
                <Icon name="Sparkles" size={20} style={{ color: "#6366f1" }} />
                AI Assistant Model
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                Choose which AI model powers the Teaching Assistant chat.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <select
                  className="input"
                  style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                  value={config.assistant_model || "haiku"}
                  onChange={(e) => {
                    var updated = { ...config, assistant_model: e.target.value };
                    setConfig(updated);
                    api.saveGlobalSettings({ globalAINotes, config: updated }).then(() => {
                      var labels = {
                        "haiku": "Haiku 4.5 (fast, low cost)",
                        "sonnet": "Sonnet 4 (higher quality)",
                        "gpt-4o-mini": "GPT-4o Mini (fast, low cost)",
                        "gpt-4o": "GPT-4o (best quality)",
                        "gemini-flash": "Gemini Flash (fast, low cost)",
                        "gemini-pro": "Gemini Pro (balanced)"
                      };
                      addToast("Assistant model set to " + (labels[e.target.value] || e.target.value), "success");
                    });
                  }}
                >
                  <optgroup label="Anthropic">
                    <option value="haiku">Haiku 4.5 — Fast, low cost ($0.80/$4 per 1M tokens)</option>
                    <option value="sonnet">Sonnet 4 — Higher quality ($3/$15 per 1M tokens)</option>
                  </optgroup>
                  <optgroup label="OpenAI">
                    <option value="gpt-4o-mini">GPT-4o Mini — Fast, low cost ($0.15/$0.60 per 1M tokens)</option>
                    <option value="gpt-4o">GPT-4o — Best quality ($2.50/$10 per 1M tokens)</option>
                  </optgroup>
                  <optgroup label="Google">
                    <option value="gemini-flash">Gemini 2.0 Flash — Fast, low cost ($0.10/$0.40 per 1M tokens)</option>
                    <option value="gemini-pro">Gemini 2.0 Pro — Balanced ($1.25/$5 per 1M tokens)</option>
                  </optgroup>
                </select>
              </div>
            </div>

            {/* Assistant Voice Selection */}
            <div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                marginBottom: "15px",
                marginTop: "25px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}>
                <Icon name="Mic" size={20} style={{ color: "#6366f1" }} />
                Assistant Voice
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                Choose the voice used for voice-mode responses.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <select
                  className="input"
                  style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                  value={config.assistant_voice || "nova"}
                  onChange={(e) => {
                    var updated = { ...config, assistant_voice: e.target.value };
                    setConfig(updated);
                    api.saveGlobalSettings({ globalAINotes, config: updated }).then(() => {
                      addToast("Voice set to " + e.target.value.charAt(0).toUpperCase() + e.target.value.slice(1), "success");
                    });
                  }}
                >
                  <option value="alloy">Alloy — Neutral, balanced</option>
                  <option value="ash">Ash — Warm, conversational</option>
                  <option value="coral">Coral — Friendly, expressive</option>
                  <option value="echo">Echo — Smooth, articulate</option>
                  <option value="fable">Fable — Storytelling, animated</option>
                  <option value="nova">Nova — Bright, engaging (default)</option>
                  <option value="onyx">Onyx — Deep, authoritative</option>
                  <option value="sage">Sage — Calm, thoughtful</option>
                  <option value="shimmer">Shimmer — Light, cheerful</option>
                </select>
              </div>
            </div>

            {/* District Portal (VPortal) Credentials */}
            <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "20px", marginTop: "20px" }}>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                marginBottom: "15px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}>
                <Icon name="Building2" size={20} style={{ color: "#6366f1" }} />
                District Portal (VPortal)
              </h3>
              <p style={{
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
                marginBottom: "15px",
              }}>
                Save your VPortal credentials to enable Focus gradebook automation and Outlook email sending.
                Credentials are stored securely on the server and never shared externally.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "400px" }}>
                <div>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
                    Email
                  </label>
                  <input
                    type="email"
                    value={vportalEmail}
                    onChange={(e) => setVportalEmail(e.target.value)}
                    placeholder="you@district.edu"
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      background: "var(--input-bg)",
                      border: "1px solid var(--input-border)",
                      borderRadius: "10px",
                      color: "var(--text-primary)",
                      fontSize: "0.9rem",
                      outline: "none",
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
                    Password
                  </label>
                  <div style={{ position: "relative" }}>
                    <input
                      type={showVportalPassword ? "text" : "password"}
                      value={vportalPassword}
                      onChange={(e) => setVportalPassword(e.target.value)}
                      placeholder={vportalConfigured ? "••••••••" : "Enter password"}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        paddingRight: "44px",
                        background: "var(--input-bg)",
                        border: "1px solid var(--input-border)",
                        borderRadius: "10px",
                        color: "var(--text-primary)",
                        fontSize: "0.9rem",
                        outline: "none",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowVportalPassword(!showVportalPassword)}
                      style={{
                        position: "absolute",
                        right: "10px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        padding: "4px",
                        color: "var(--text-secondary)",
                        display: "flex",
                        alignItems: "center",
                      }}
                      title={showVportalPassword ? "Hide password" : "Show password"}
                    >
                      <Icon name={showVportalPassword ? "EyeOff" : "Eye"} size={18} />
                    </button>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <button
                    onClick={async () => {
                      if (!vportalEmail || !vportalPassword) {
                        addToast("Please enter both email and password", "error");
                        return;
                      }
                      setVportalSaving(true);
                      try {
                        await api.savePortalCredentials(vportalEmail, vportalPassword);
                        setVportalConfigured(true);
                        setVportalPassword("");
                        setShowVportalPassword(false);
                        addToast("VPortal credentials saved", "success");
                      } catch (err) {
                        addToast("Failed to save credentials: " + err.message, "error");
                      }
                      setVportalSaving(false);
                    }}
                    className="btn btn-primary"
                    style={{ padding: "8px 16px" }}
                    disabled={vportalSaving}
                  >
                    {vportalSaving ? "Saving..." : "Save Credentials"}
                  </button>
                  {vportalConfigured && (
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "0.8rem",
                      color: "var(--success)",
                    }}>
                      <Icon name="CheckCircle2" size={14} />
                      Configured
                    </span>
                  )}
                </div>
              </div>
            </div>
              </>
            )}

            {/* Integration Tab (now Tools) */}
            {settingsTab === "integration" && (
              <div data-tutorial="settings-integration">
            {/* Available EdTech Tools */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="Laptop" size={20} />
                Available EdTech Tools
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Select the tools your school provides. Lesson plans will
                only suggest activities using these tools.
              </p>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: "10px",
                  maxHeight: "300px",
                  overflowY: "auto",
                  padding: "10px",
                  background: "var(--input-bg)",
                  borderRadius: "12px",
                  border: "1px solid var(--input-border)",
                }}
              >
                {EDTECH_TOOLS.map((tool) => (
                  <label
                    key={tool.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      cursor: "pointer",
                      padding: "10px",
                      borderRadius: "8px",
                      background: config.availableTools?.includes(
                        tool.id,
                      )
                        ? "rgba(99,102,241,0.15)"
                        : "transparent",
                      border: config.availableTools?.includes(tool.id)
                        ? "1px solid rgba(99,102,241,0.3)"
                        : "1px solid transparent",
                      transition: "all 0.2s",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={
                        config.availableTools?.includes(tool.id) ||
                        false
                      }
                      onChange={(e) => {
                        const newTools = e.target.checked
                          ? [...(config.availableTools || []), tool.id]
                          : (config.availableTools || []).filter(
                              (t) => t !== tool.id,
                            );
                        setConfig((prev) => ({
                          ...prev,
                          availableTools: newTools,
                        }));
                      }}
                      style={{
                        width: "16px",
                        height: "16px",
                        accentColor: "var(--accent-primary)",
                        cursor: "pointer",
                        marginTop: "2px",
                      }}
                    />
                    <div>
                      <div
                        style={{ fontWeight: 600, fontSize: "0.9rem" }}
                      >
                        {tool.name}
                      </div>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        {tool.category} • {tool.description}
                      </div>
                    </div>
                  </label>
                ))}

                {/* Custom Tools */}
                {customTools.map((tool) => (
                  <label
                    key={tool}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      cursor: "pointer",
                      padding: "10px",
                      borderRadius: "8px",
                      background: config.availableTools?.includes(
                        `custom:${tool}`,
                      )
                        ? "rgba(16,185,129,0.15)"
                        : "transparent",
                      border: config.availableTools?.includes(
                        `custom:${tool}`,
                      )
                        ? "1px solid rgba(16,185,129,0.3)"
                        : "1px solid rgba(255,255,255,0.1)",
                      transition: "all 0.2s",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={
                        config.availableTools?.includes(
                          `custom:${tool}`,
                        ) || false
                      }
                      onChange={(e) => {
                        const toolId = `custom:${tool}`;
                        const newTools = e.target.checked
                          ? [...(config.availableTools || []), toolId]
                          : (config.availableTools || []).filter(
                              (t) => t !== toolId,
                            );
                        setConfig((prev) => ({
                          ...prev,
                          availableTools: newTools,
                        }));
                      }}
                      style={{
                        width: "16px",
                        height: "16px",
                        accentColor: "#10b981",
                        cursor: "pointer",
                        marginTop: "2px",
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <div
                        style={{ fontWeight: 600, fontSize: "0.9rem" }}
                      >
                        {tool}
                      </div>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        Custom • Added by you
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        setCustomTools(
                          customTools.filter((t) => t !== tool),
                        );
                        setConfig((prev) => ({
                          ...prev,
                          availableTools: (
                            prev.availableTools || []
                          ).filter((t) => t !== `custom:${tool}`),
                        }));
                      }}
                      style={{
                        background: "rgba(239,68,68,0.2)",
                        border: "none",
                        borderRadius: "4px",
                        padding: "4px 8px",
                        color: "#ef4444",
                        cursor: "pointer",
                        fontSize: "0.75rem",
                      }}
                    >
                      Remove
                    </button>
                  </label>
                ))}
              </div>

              {/* Add Custom Tool */}
              <div style={{ marginTop: "15px" }}>
                <label
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Add a custom tool not in the list:
                </label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="text"
                    className="input"
                    value={newCustomTool}
                    onChange={(e) => setNewCustomTool(e.target.value)}
                    placeholder="e.g., Formative, Socrative, Classkick..."
                    style={{ flex: 1 }}
                    onKeyPress={(e) => {
                      if (e.key === "Enter" && newCustomTool.trim()) {
                        if (
                          !customTools.includes(newCustomTool.trim())
                        ) {
                          setCustomTools([
                            ...customTools,
                            newCustomTool.trim(),
                          ]);
                        }
                        setNewCustomTool("");
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      if (
                        newCustomTool.trim() &&
                        !customTools.includes(newCustomTool.trim())
                      ) {
                        setCustomTools([
                          ...customTools,
                          newCustomTool.trim(),
                        ]);
                        setNewCustomTool("");
                      }
                    }}
                    className="btn btn-primary"
                    style={{ padding: "8px 16px" }}
                    disabled={!newCustomTool.trim()}
                  >
                    <Icon name="Plus" size={16} /> Add
                  </button>
                </div>
              </div>

              <div
                style={{
                  marginTop: "15px",
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                  alignItems: "center",
                }}
              >
                <button
                  onClick={() => {
                    const allTools = [
                      ...EDTECH_TOOLS.map((t) => t.id),
                      ...customTools.map((t) => `custom:${t}`),
                    ];
                    setConfig((prev) => ({
                      ...prev,
                      availableTools: allTools,
                    }));
                  }}
                  className="btn btn-secondary"
                  style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                >
                  Select All
                </button>
                <button
                  onClick={() =>
                    setConfig((prev) => ({
                      ...prev,
                      availableTools: [],
                    }))
                  }
                  className="btn btn-secondary"
                  style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                >
                  Clear All
                </button>
                <span
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  {config.availableTools?.length || 0} tools selected
                  {customTools.length > 0 &&
                    ` (${customTools.length} custom)`}
                </span>
              </div>
            </div>

            {/* Assessment Platform Templates */}
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "20px",
                marginTop: "20px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="FileSpreadsheet" size={20} />
                Assessment Platform Templates
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Upload sample templates from your assessment platforms (e.g., Wayground, Mastery Connect).
                Graider will match the format when exporting assessments.
              </p>

              {/* Upload New Template */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--glass-bg)",
                  borderRadius: "12px",
                  border: "1px dashed var(--glass-border)",
                  marginBottom: "15px",
                }}
              >
                <div style={{ display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: "150px" }}>
                    <label className="label" style={{ fontSize: "0.8rem" }}>Platform Name</label>
                    <select
                      className="input"
                      id="template-platform"
                      style={{ fontSize: "0.9rem" }}
                    >
                      <option value="wayground">Wayground</option>
                      <option value="mastery_connect">Mastery Connect</option>
                      <option value="edulastic">Edulastic</option>
                      <option value="illuminate">Illuminate</option>
                      <option value="schoology">Schoology</option>
                      <option value="custom">Other/Custom</option>
                    </select>
                  </div>
                  <div style={{ flex: 1, minWidth: "150px" }}>
                    <label className="label" style={{ fontSize: "0.8rem" }}>Template Name</label>
                    <input
                      type="text"
                      className="input"
                      id="template-name"
                      placeholder="e.g., Quiz Import Template"
                      style={{ fontSize: "0.9rem" }}
                    />
                  </div>
                  <div>
                    <input
                      type="file"
                      id="template-file"
                      accept=".csv,.xlsx,.xls,.json,.txt"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files[0];
                        if (!file) return;

                        const platform = document.getElementById("template-platform").value;
                        const name = document.getElementById("template-name").value || file.name;

                        setUploadingTemplate(true);
                        try {
                          const result = await api.uploadAssessmentTemplate(file, platform, name);
                          if (result.success) {
                            addToast(`Template "${name}" uploaded successfully!`, "success");
                            // Refresh templates list
                            const templates = await api.getAssessmentTemplates();
                            setAssessmentTemplates(templates.templates || []);
                          } else {
                            addToast("Error: " + (result.error || "Upload failed"), "error");
                          }
                        } catch (err) {
                          addToast("Error uploading template: " + err.message, "error");
                        } finally {
                          setUploadingTemplate(false);
                          e.target.value = "";
                        }
                      }}
                    />
                    <button
                      onClick={() => document.getElementById("template-file").click()}
                      className="btn btn-primary"
                      style={{ padding: "8px 16px" }}
                      disabled={uploadingTemplate}
                    >
                      {uploadingTemplate ? (
                        <>
                          <Icon name="Loader2" size={16} className="spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <Icon name="Upload" size={16} />
                          Upload Template
                        </>
                      )}
                    </button>
                  </div>
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "10px" }}>
                  Supported formats: CSV, Excel (.xlsx), JSON, TXT
                </p>
              </div>

              {/* Existing Templates */}
              {assessmentTemplates.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                  }}
                >
                  <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                    Uploaded Templates ({assessmentTemplates.length})
                  </label>
                  {assessmentTemplates.map((template) => (
                    <div
                      key={template.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "12px 15px",
                        background: "var(--glass-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--glass-border)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                        <Icon
                          name={template.extension === ".csv" ? "Table" : template.extension === ".xlsx" ? "FileSpreadsheet" : "FileText"}
                          size={20}
                          style={{ color: "var(--accent-primary)" }}
                        />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                            {template.name}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {template.platform} • {template.structure?.columns?.length || 0} columns • {template.extension}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        {template.structure?.columns && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              color: "var(--text-muted)",
                              maxWidth: "200px",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                            title={template.structure.columns.join(", ")}
                          >
                            {template.structure.columns.slice(0, 3).join(", ")}
                            {template.structure.columns.length > 3 && "..."}
                          </span>
                        )}
                        <button
                          onClick={async () => {
                            try {
                              await api.deleteAssessmentTemplate(template.id);
                              setAssessmentTemplates(assessmentTemplates.filter(t => t.id !== template.id));
                              addToast("Template deleted", "info");
                            } catch (err) {
                              addToast("Error deleting template", "error");
                            }
                          }}
                          style={{
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "none",
                            borderRadius: "6px",
                            padding: "6px 10px",
                            color: "#ef4444",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            fontSize: "0.8rem",
                          }}
                        >
                          <Icon name="Trash2" size={14} />
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {assessmentTemplates.length === 0 && (
                <div
                  style={{
                    textAlign: "center",
                    padding: "20px",
                    color: "var(--text-muted)",
                    fontSize: "0.85rem",
                  }}
                >
                  No templates uploaded yet. Upload a sample file from your assessment platform to get started.
                </div>
              )}
            </div>

            {/* Cloud Sync Section */}
            <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "20px", marginTop: "20px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="Cloud" size={20} />
                Cloud Data Sync
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "15px" }}>
                Upload all your local settings, rubrics, assignments, grades, and student data to the cloud so they persist across deployments and devices.
              </p>
              <button
                className="btn btn-primary"
                disabled={syncingCloud}
                onClick={async () => {
                  setSyncingCloud(true);
                  try {
                    const resp = await fetch("/api/sync-to-cloud", {
                      method: "POST",
                      headers: { "Content-Type": "application/json", Authorization: "Bearer " + (window._authToken || "") },
                    });
                    const data = await resp.json();
                    if (data.error) {
                      addToast(data.error, "error");
                    } else {
                      const summary = data.summary || {};
                      const parts = Object.entries(summary).map(function(e) { return e[0] + ": " + e[1]; });
                      addToast("Synced to cloud! " + parts.join(", "), "success");
                    }
                  } catch (err) {
                    addToast("Sync failed: " + err.message, "error");
                  } finally {
                    setSyncingCloud(false);
                  }
                }}
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <Icon name={syncingCloud ? "Loader2" : "Upload"} size={16} />
                {syncingCloud ? "Syncing..." : "Sync Data to Cloud"}
              </button>
            </div>
              </div>
            )}

            {/* Classroom Tab */}
            {settingsTab === "classroom" && (
              <>
            {/* Add Student from Screenshot Section */}
            <div
              data-tutorial="settings-classroom"
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "25px",
                marginTop: "25px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Camera"
                  size={20}
                  style={{ color: "#8b5cf6" }}
                />
                Add Student from Screenshot
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Paste or upload a screenshot of student info - AI will extract and add to roster
              </p>

              <div style={{ display: "flex", gap: "10px", marginBottom: "15px", flexWrap: "wrap" }}>
                <button
                  onClick={async () => {
                    try {
                      const clipboardItems = await navigator.clipboard.read();
                      for (const item of clipboardItems) {
                        if (item.types.includes("image/png")) {
                          const blob = await item.getType("image/png");
                          const reader = new FileReader();
                          reader.onload = async (e) => {
                            const base64 = e.target.result;
                            setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                            try {
                              const authHdrs = await getAuthHeaders();
                              const response = await fetch("/api/extract-student-from-image", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", ...authHdrs },
                                body: JSON.stringify({ image: base64 }),
                              });
                              const data = await response.json();
                              if (data.error) {
                                setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                              } else {
                                setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                              }
                            } catch (err) {
                              setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                            }
                          };
                          reader.readAsDataURL(blob);
                          return;
                        }
                      }
                      addToast("No image found in clipboard. Copy a screenshot first.", "warning");
                    } catch (err) {
                      addToast("Could not access clipboard: " + err.message, "error");
                    }
                  }}
                  className="btn btn-primary"
                >
                  <Icon name="Clipboard" size={18} />
                  Paste from Clipboard
                </button>
                <label className="btn btn-secondary" style={{ cursor: "pointer" }}>
                  <Icon name="Upload" size={18} />
                  Upload Image
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = async (ev) => {
                        const base64 = ev.target.result;
                        setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                        try {
                          const authHdrs = await getAuthHeaders();
                          const response = await fetch("/api/extract-student-from-image", {
                            method: "POST",
                            headers: { "Content-Type": "application/json", ...authHdrs },
                            body: JSON.stringify({ image: base64 }),
                          });
                          const data = await response.json();
                          if (data.error) {
                            setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                          } else {
                            setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                          }
                        } catch (err) {
                          setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                        }
                      };
                      reader.readAsDataURL(file);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>

            {/* Period/Class Upload Section */}
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "25px",
                marginTop: "25px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Clock"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Class Periods
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload separate rosters for each class period, or import directly from Focus SIS
              </p>

              <input
                ref={periodInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                style={{ display: "none" }}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (!newPeriodName.trim()) {
                    addToast(
                      "Please enter a period name first",
                      "warning",
                    );
                    e.target.value = "";
                    return;
                  }
                  setUploadingPeriod(true);
                  try {
                    const result = await api.uploadPeriod(
                      file,
                      newPeriodName,
                    );
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      const periodsData = await api.listPeriods();
                      setPeriods(periodsData.periods || []);
                      setNewPeriodName("");
                    }
                  } catch (err) {
                    addToast("Upload failed: " + err.message, "error");
                  }
                  setUploadingPeriod(false);
                  e.target.value = "";
                }}
              />

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  marginBottom: "15px",
                }}
              >
                <input
                  type="text"
                  className="input"
                  placeholder="Period name (e.g., Period 1, Block A)"
                  value={newPeriodName}
                  onChange={(e) => setNewPeriodName(e.target.value)}
                  style={{ maxWidth: "250px" }}
                />
                <button
                  onClick={() => periodInputRef.current?.click()}
                  className="btn btn-secondary"
                  disabled={uploadingPeriod || !newPeriodName.trim()}
                  style={{
                    opacity:
                      !newPeriodName.trim() || uploadingPeriod
                        ? 0.5
                        : 1,
                    cursor:
                      !newPeriodName.trim() || uploadingPeriod
                        ? "not-allowed"
                        : "pointer",
                  }}
                  title={
                    !newPeriodName.trim()
                      ? "Enter a period name first"
                      : ""
                  }
                >
                  <Icon name="Upload" size={18} />
                  {uploadingPeriod
                    ? "Uploading..."
                    : "Upload CSV/Excel"}
                </button>
                <div style={{ position: "relative" }}>
                  <button
                    className="btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      const el = e.currentTarget.nextElementSibling;
                      if (el) el.style.display = el.style.display === "none" ? "block" : "none";
                    }}
                    style={{ padding: "8px", minWidth: 0, borderRadius: "50%", width: "36px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center" }}
                    title="How to export roster from Focus"
                  >
                    <Icon name="HelpCircle" size={18} style={{ color: "var(--accent-primary)" }} />
                  </button>
                  <div style={{ display: "none", position: "absolute", top: "42px", right: 0, zIndex: 100, width: "320px", background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "12px", padding: "16px", boxShadow: "0 8px 30px rgba(0,0,0,0.3)" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="FileSpreadsheet" size={16} style={{ color: "var(--accent-primary)" }} />
                      Export from Focus SIS
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                      <p style={{ margin: "0 0 6px" }}><strong>Reports {'>'} Student Listings {'>'} CSV</strong></p>
                      <p style={{ margin: "0 0 6px" }}>Required columns: Student ID, First Name, Last Name, Email</p>
                      <p style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>Column names are detected automatically (e.g. "student_id", "StudentID", or "Student ID" all work).</p>
                      <p style={{ margin: 0, color: "var(--text-muted)" }}>Combined "Student Name" columns with "Last, First" format are also supported.</p>
                    </div>
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "15px" }}>
                {!newPeriodName.trim() && (
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      margin: 0,
                    }}
                  >
                    Enter a period name above, then click Upload
                  </p>
                )}
                <button
                  onClick={async () => {
                    if (focusImporting) return;
                    setFocusImporting(true);
                    setFocusImportProgress("Starting Focus import...");
                    try {
                      const res = await api.importFromFocus();
                      if (res.error) {
                        addToast(res.error, "error");
                        setFocusImporting(false);
                        return;
                      }
                      // Poll for status
                      const pollInterval = setInterval(async () => {
                        try {
                          const status = await api.getFocusImportStatus();
                          setFocusImportProgress(status.progress || "");
                          if (status.status === "completed") {
                            clearInterval(pollInterval);
                            setFocusImporting(false);
                            setFocusImportProgress("");
                            const r = status.result || {};
                            addToast("Imported " + (r.periods_imported || 0) + " periods, " + (r.total_students || 0) + " students, " + (r.total_contacts || 0) + " parent contacts", "success");
                            const periodsData = await api.listPeriods();
                            setPeriods(periodsData.periods || []);
                          } else if (status.status === "failed") {
                            clearInterval(pollInterval);
                            setFocusImporting(false);
                            setFocusImportProgress("");
                            addToast("Focus import failed: " + (status.error || "Unknown error"), "error");
                          }
                        } catch (err) {
                          clearInterval(pollInterval);
                          setFocusImporting(false);
                          setFocusImportProgress("");
                        }
                      }, 2000);
                    } catch (err) {
                      addToast("Failed to start Focus import: " + err.message, "error");
                      setFocusImporting(false);
                      setFocusImportProgress("");
                    }
                  }}
                  className="btn btn-secondary"
                  disabled={focusImporting}
                  style={{ marginLeft: "auto", opacity: focusImporting ? 0.6 : 1, whiteSpace: "nowrap" }}
                >
                  <Icon name="Download" size={18} />
                  {focusImporting ? "Importing..." : "Import from Focus"}
                </button>
              </div>

              {/* Focus import progress banner */}
              {focusImporting && focusImportProgress && (
                <div style={{
                  padding: "10px 15px",
                  marginBottom: "15px",
                  background: "rgba(59, 130, 246, 0.1)",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  borderRadius: "8px",
                  fontSize: "0.85rem",
                  color: "#60a5fa",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}>
                  <Icon name="Loader" size={16} style={{ animation: "spin 1s linear infinite" }} />
                  {focusImportProgress}
                </div>
              )}

              {/* Period Cards - Expandable */}
              {sortedPeriods.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {sortedPeriods.map((period) => (
                    <div key={period.filename} style={{ borderRadius: "8px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
                      {/* Period Header Row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          padding: "10px 15px",
                          background: expandedPeriod === period.filename ? "rgba(245, 158, 11, 0.08)" : "var(--input-bg)",
                          cursor: "pointer",
                        }}
                        onClick={async () => {
                          if (expandedPeriod === period.filename) {
                            setExpandedPeriod(null);
                            setExpandedStudents([]);
                            setEditingStudentId(null);
                            setAddingStudent(false);
                            return;
                          }
                          setExpandedPeriod(period.filename);
                          setLoadingExpandedStudents(true);
                          setEditingStudentId(null);
                          setAddingStudent(false);
                          try {
                            const [studentsRes, contactsRes] = await Promise.all([
                              api.getPeriodStudents(period.filename),
                              api.getParentContacts(),
                            ]);
                            const students = studentsRes.students || [];
                            const contacts = contactsRes.contacts || {};
                            // Merge contact info into student list
                            const merged = students.map(s => {
                              const contact = contacts[s.id] || {};
                              return {
                                ...s,
                                parent_emails: contact.parent_emails || [],
                                parent_phones: contact.parent_phones || [],
                              };
                            });
                            setExpandedStudents(merged);
                          } catch (err) {
                            addToast("Failed to load students: " + err.message, "error");
                            setExpandedStudents([]);
                          }
                          setLoadingExpandedStudents(false);
                        }}
                      >
                        <Icon
                          name={expandedPeriod === period.filename ? "ChevronDown" : "ChevronRight"}
                          size={16}
                          style={{ color: "#f59e0b", flexShrink: 0 }}
                        />
                        <Icon name="Users" size={16} style={{ color: "#f59e0b", flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "8px" }}>
                            {period.period_name}
                            {period.course_codes && period.course_codes.length > 0 && (
                              <span style={{ fontSize: "0.7rem", padding: "1px 6px", borderRadius: "4px", background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", fontWeight: 500 }}>
                                {period.course_codes.join(", ")}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                            {period.row_count} students{period.imported_from === "focus" ? " (Focus SIS)" : ""}
                          </div>
                        </div>
                        <select
                          value={period.class_level || "standard"}
                          onClick={(e) => e.stopPropagation()}
                          onChange={async (e) => {
                            e.stopPropagation();
                            const newLevel = e.target.value;
                            await api.updatePeriodLevel(period.filename, newLevel);
                            const data = await api.listPeriods();
                            setPeriods(data.periods || []);
                          }}
                          style={{
                            padding: "4px 8px",
                            borderRadius: "6px",
                            border: "1px solid var(--glass-border)",
                            background: period.class_level === "advanced" ? "rgba(139, 92, 246, 0.2)" : period.class_level === "support" ? "rgba(244, 114, 182, 0.2)" : "var(--input-bg)",
                            color: period.class_level === "advanced" ? "#a78bfa" : period.class_level === "support" ? "#f472b6" : "var(--text-primary)",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          <option value="standard">Standard</option>
                          <option value="advanced">Advanced</option>
                          <option value="support">Support</option>
                        </select>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (confirm("Delete " + period.period_name + "?")) {
                              await api.deletePeriod(period.filename);
                              const data = await api.listPeriods();
                              setPeriods(data.periods || []);
                              if (expandedPeriod === period.filename) {
                                setExpandedPeriod(null);
                                setExpandedStudents([]);
                              }
                            }
                          }}
                          style={{ padding: "4px 6px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>

                      {/* Expanded Student List */}
                      {expandedPeriod === period.filename && (
                        <div style={{ borderTop: "1px solid var(--glass-border)", padding: "10px 15px", background: "var(--bg-secondary)" }}>
                          {loadingExpandedStudents ? (
                            <div style={{ textAlign: "center", padding: "20px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                              <Icon name="Loader" size={18} style={{ animation: "spin 1s linear infinite", marginRight: "8px" }} />
                              Loading students...
                            </div>
                          ) : expandedStudents.length === 0 ? (
                            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", textAlign: "center", padding: "10px" }}>No students found</p>
                          ) : (
                            <div style={{ overflowX: "auto" }}>
                              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                                <thead>
                                  <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Student Name</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>ID</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Emails</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Phones</th>
                                    <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600, width: "80px" }}>Actions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedStudents.map((student) => (
                                    <tr key={student.id || student.full} style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                      {editingStudentId === student.id ? (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.student_name || ""} onChange={(e) => setEditStudentData({...editStudentData, student_name: e.target.value})} style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-muted)" }}>{student.id}</td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_emails || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_emails: e.target.value})} placeholder="email1, email2" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_phones || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_phones: e.target.value})} placeholder="(386) 555-1234" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            <button
                                              onClick={async () => {
                                                try {
                                                  const emails = editStudentData.parent_emails ? editStudentData.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                                  const phones = editStudentData.parent_phones ? editStudentData.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                                  await api.updateStudent({
                                                    period_filename: period.filename,
                                                    student_id: student.id,
                                                    student_name: editStudentData.student_name,
                                                    parent_emails: emails,
                                                    parent_phones: phones,
                                                  });
                                                  setEditingStudentId(null);
                                                  // Refresh
                                                  const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                  const contacts = contactsRes.contacts || {};
                                                  setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                  addToast("Student updated", "success");
                                                } catch (err) {
                                                  addToast("Update failed: " + err.message, "error");
                                                }
                                              }}
                                              style={{ padding: "2px 6px", background: "rgba(74, 222, 128, 0.2)", border: "1px solid rgba(74, 222, 128, 0.4)", borderRadius: "4px", color: "#4ade80", cursor: "pointer", fontSize: "0.75rem", marginRight: "4px" }}
                                            >Save</button>
                                            <button
                                              onClick={() => setEditingStudentId(null)}
                                              style={{ padding: "2px 6px", background: "none", border: "1px solid var(--glass-border)", borderRadius: "4px", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.75rem" }}
                                            >Cancel</button>
                                          </td>
                                        </>
                                      ) : (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>{student.full || (student.first + " " + student.last)}</td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-secondary)" }}>{student.id || "\u2014"}</td>
                                          <td style={{ padding: "6px 8px", color: student.parent_emails.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_emails.length > 0 ? student.parent_emails.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", color: student.parent_phones.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_phones.length > 0 ? student.parent_phones.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            {student.id && (
                                              <>
                                                <button
                                                  onClick={() => {
                                                    setEditingStudentId(student.id);
                                                    setEditStudentData({
                                                      student_name: student.full || (student.first + " " + student.last),
                                                      parent_emails: student.parent_emails.join(", "),
                                                      parent_phones: student.parent_phones.join(", "),
                                                    });
                                                  }}
                                                  title="Edit"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Pencil" size={13} /></button>
                                                <button
                                                  onClick={async () => {
                                                    if (!confirm("Remove " + (student.full || student.first + " " + student.last) + " from this period?")) return;
                                                    try {
                                                      await api.removeStudent({ period_filename: period.filename, student_id: student.id });
                                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                      const contacts = contactsRes.contacts || {};
                                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                      const periodsData = await api.listPeriods();
                                                      setPeriods(periodsData.periods || []);
                                                      addToast("Student removed", "success");
                                                    } catch (err) {
                                                      addToast("Remove failed: " + err.message, "error");
                                                    }
                                                  }}
                                                  title="Remove"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Trash2" size={13} /></button>
                                              </>
                                            )}
                                          </td>
                                        </>
                                      )}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Add Student Form */}
                          {addingStudent ? (
                            <div style={{ marginTop: "10px", padding: "10px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                                <input type="text" placeholder="Student Name (Last; First)" value={newStudent.name} onChange={(e) => setNewStudent({...newStudent, name: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Student ID" value={newStudent.student_id} onChange={(e) => setNewStudent({...newStudent, student_id: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Grade (e.g., 06)" value={newStudent.grade} onChange={(e) => setNewStudent({...newStudent, grade: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Emails (comma-separated)" value={newStudent.parent_emails} onChange={(e) => setNewStudent({...newStudent, parent_emails: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Phones (comma-separated)" value={newStudent.parent_phones} onChange={(e) => setNewStudent({...newStudent, parent_phones: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                              </div>
                              <div style={{ display: "flex", gap: "8px" }}>
                                <button
                                  onClick={async () => {
                                    if (!newStudent.name.trim()) { addToast("Student name is required", "warning"); return; }
                                    try {
                                      const emails = newStudent.parent_emails ? newStudent.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                      const phones = newStudent.parent_phones ? newStudent.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                      const res = await api.addStudent({
                                        period_filename: period.filename,
                                        student_name: newStudent.name,
                                        student_id: newStudent.student_id,
                                        grade: newStudent.grade,
                                        parent_emails: emails,
                                        parent_phones: phones,
                                      });
                                      if (res.error) { addToast(res.error, "error"); return; }
                                      setNewStudent({ name: '', student_id: '', grade: '', parent_emails: '', parent_phones: '' });
                                      setAddingStudent(false);
                                      // Refresh
                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                      const contacts = contactsRes.contacts || {};
                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                      const periodsData = await api.listPeriods();
                                      setPeriods(periodsData.periods || []);
                                      addToast("Student added", "success");
                                    } catch (err) {
                                      addToast("Add failed: " + err.message, "error");
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Add Student</button>
                                <button
                                  onClick={() => { setAddingStudent(false); setNewStudent({ name: '', student_id: '', grade: '', parent_emails: '', parent_phones: '' }); }}
                                  className="btn btn-secondary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setAddingStudent(true)}
                              style={{
                                marginTop: "10px",
                                padding: "6px 12px",
                                background: "none",
                                border: "1px dashed var(--glass-border)",
                                borderRadius: "6px",
                                color: "var(--text-secondary)",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                width: "100%",
                                justifyContent: "center",
                              }}
                            >
                              <Icon name="Plus" size={14} />
                              Add Student
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* IEP/504 Accommodations Section */}
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "25px",
                marginTop: "25px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Heart"
                  size={20}
                  style={{ color: "#f472b6" }}
                />
                IEP/504 Accommodations
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 8px",
                    background: "rgba(74, 222, 128, 0.2)",
                    color: "#4ade80",
                    borderRadius: "4px",
                    fontWeight: 500,
                  }}
                >
                  FERPA Compliant
                </span>
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Assign accommodation presets to students for
                personalized feedback. Only accommodation types are sent
                to AI - never student names or IDs.
              </p>

              {/* Available Presets */}
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: "12px",
                    fontSize: "0.95rem",
                  }}
                >
                  Available Presets
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(200px, 1fr))",
                    gap: "10px",
                  }}
                >
                  {accommodationPresets.map((preset) => (
                    <div
                      key={preset.id}
                      style={{
                        padding: "12px",
                        background: "var(--input-bg)",
                        borderRadius: "8px",
                        border: "1px solid var(--input-border)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          marginBottom: "6px",
                        }}
                      >
                        <Icon
                          name={preset.icon || "FileText"}
                          size={16}
                          style={{ color: "#f472b6" }}
                        />
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: "0.85rem",
                          }}
                        >
                          {preset.name}
                        </span>
                      </div>
                      <p
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          margin: 0,
                        }}
                      >
                        {preset.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Student Accommodations List */}
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    Student Accommodations (
                    {Object.keys(studentAccommodations).length}{" "}
                    students)
                  </div>
                  <button
                    onClick={() =>
                      setAccommodationModal({
                        show: true,
                        studentId: null,
                      })
                    }
                    className="btn btn-primary"
                    style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  >
                    <Icon name="Plus" size={14} />
                    Add Student
                  </button>
                </div>

                {Object.keys(studentAccommodations).length > 0 ? (
                  <div
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    {Object.entries(studentAccommodations).map(
                      ([studentId, data]) => (
                        <div
                          key={studentId}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "10px 14px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--input-border)",
                          }}
                        >
                          <div>
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: "0.9rem",
                              }}
                            >
                              {data.student_name || "ID: " + studentId}
                            </div>
                            <div
                              style={{
                                display: "flex",
                                gap: "6px",
                                marginTop: "4px",
                                flexWrap: "wrap",
                              }}
                            >
                              {data.presets.map((preset) => (
                                <span
                                  key={preset.id}
                                  style={{
                                    padding: "2px 8px",
                                    background:
                                      preset.id === "ell_support"
                                        ? "rgba(96, 165, 250, 0.15)"
                                        : "rgba(244, 114, 182, 0.15)",
                                    color:
                                      preset.id === "ell_support"
                                        ? "#60a5fa"
                                        : "#f472b6",
                                    borderRadius: "4px",
                                    fontSize: "0.7rem",
                                    fontWeight: 500,
                                  }}
                                >
                                  {preset.name}
                                </span>
                              ))}
                              {data.custom_notes && (
                                <span
                                  style={{
                                    padding: "2px 8px",
                                    background:
                                      "rgba(99, 102, 241, 0.15)",
                                    color: "#818cf8",
                                    borderRadius: "4px",
                                    fontSize: "0.7rem",
                                    fontWeight: 500,
                                  }}
                                >
                                  Custom Notes
                                </span>
                              )}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              onClick={async () => {
                                setSelectedAccommodationPresets(
                                  data.presets.map((p) => p.id),
                                );
                                setAccommodationCustomNotes(
                                  data.custom_notes || "",
                                );
                                // Load ELL language if ELL Support is active
                                if (
                                  data.presets.some(
                                    (p) => p.id === "ell_support",
                                  )
                                ) {
                                  try {
                                    const ellData =
                                      await api.getEllStudents();
                                    setAccommEllLanguage(
                                      ellData?.[studentId]?.language ||
                                        "",
                                    );
                                  } catch (e) {
                                    setAccommEllLanguage("");
                                  }
                                } else {
                                  setAccommEllLanguage("");
                                }
                                setAccommodationModal({
                                  show: true,
                                  studentId,
                                });
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px" }}
                            >
                              <Icon name="Edit2" size={14} />
                            </button>
                            <button
                              onClick={async () => {
                                if (
                                  confirm(
                                    "Remove accommodations for this student?",
                                  )
                                ) {
                                  try {
                                    await api.deleteStudentAccommodation(
                                      studentId,
                                    );
                                    const newData = {
                                      ...studentAccommodations,
                                    };
                                    delete newData[studentId];
                                    setStudentAccommodations(newData);
                                  } catch (err) {
                                    addToast(
                                      "Error removing accommodation: " +
                                        err.message,
                                      "error",
                                    );
                                  }
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                color: "#ef4444",
                              }}
                            >
                              <Icon name="Trash2" size={14} />
                            </button>
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "30px",
                      textAlign: "center",
                      background: "var(--input-bg)",
                      borderRadius: "8px",
                      border: "1px dashed var(--input-border)",
                    }}
                  >
                    <Icon
                      name="Heart"
                      size={32}
                      style={{
                        color: "var(--text-muted)",
                        marginBottom: "10px",
                      }}
                    />
                    <p
                      style={{
                        color: "var(--text-muted)",
                        fontSize: "0.85rem",
                        margin: 0,
                      }}
                    >
                      No students with accommodations yet. Add students
                      from your roster.
                    </p>
                  </div>
                )}
              </div>

              {/* Import/Export */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Import & Export
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <label
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem", cursor: "pointer" }}
                  >
                    <Icon name="Upload" size={16} />
                    Import from CSV
                    <input
                      type="file"
                      accept=".csv"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        try {
                          const result = await api.importAccommodations(
                            file,
                            "student_id",
                            "accommodation_type",
                            "accommodation_notes",
                          );
                          addToast(
                            "Import complete: " +
                              result.imported +
                              " imported, " +
                              result.skipped +
                              " skipped",
                            "success",
                          );
                          // Reload accommodations
                          const data =
                            await api.getStudentAccommodations();
                          if (data.accommodations)
                            setStudentAccommodations(
                              data.accommodations,
                            );
                        } catch (err) {
                          addToast(
                            "Import failed: " + err.message,
                            "error",
                          );
                        }
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <button
                    onClick={async () => {
                      try {
                        const data = await api.exportAccommodations();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download =
                          "graider_accommodations_" +
                          new Date().toISOString().split("T")[0] +
                          ".json";
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast(
                          "Export failed: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export Accommodations
                  </button>
                </div>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginTop: "10px",
                  }}
                >
                  CSV should have columns: student_id,
                  accommodation_type, accommodation_notes (optional)
                </p>
              </div>
            </div>

            {/* Parent Contacts Upload */}
            <div style={{ marginTop: "30px" }}>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Contact"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Parent Contacts
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload class list Excel file with parent email and phone
                columns. Used for Focus export and Outlook email generation.
              </p>

              <input
                ref={parentContactsInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: "none" }}
                onChange={async (e) => {
                  var file = e.target.files?.[0];
                  if (!file) return;
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.previewParentContacts(file);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      var suggested = result.suggested_mapping || {};
                      setParentContactMapping({
                        show: true,
                        preview: result,
                        mapping: {
                          name_col: suggested.name_col || "",
                          name_format: suggested.name_format || "last_first",
                          id_col: suggested.id_col || "",
                          id_strip_digits: suggested.id_strip_digits || 0,
                          contact_cols: suggested.contact_cols || [],
                          period_col: suggested.period_col || "",
                        },
                      });
                    }
                  } catch (err) {
                    addToast("Upload failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                  e.target.value = "";
                }}
              />

              <button
                onClick={() => parentContactsInputRef.current?.click()}
                className="btn btn-secondary"
                disabled={uploadingParentContacts}
                style={{ marginBottom: "15px" }}
              >
                <Icon name="Upload" size={18} />
                {uploadingParentContacts ? "Reading file..." : "Upload Class List (.xlsx, .csv)"}
              </button>

              {parentContacts && parentContacts.count > 0 && (
                <div
                  style={{
                    padding: "12px 15px",
                    background: "var(--input-bg)",
                    borderRadius: "8px",
                    border: "1px solid var(--glass-border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                    {parentContacts.count} students loaded
                  </div>
                  <div style={{ color: "var(--text-secondary)" }}>
                    {parentContacts.with_email} with parent email
                    {parentContacts.without_email > 0 && (
                      <span style={{ color: "#f59e0b" }}>
                        {" "}({parentContacts.without_email} missing email)
                      </span>
                    )}
                  </div>
                  {parentContacts.period_stats && (
                    <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {Object.entries(parentContacts.period_stats).map(function(entry) {
                        return (
                          <span
                            key={entry[0]}
                            style={{
                              padding: "2px 8px",
                              background: "rgba(99,102,241,0.15)",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                            }}
                          >
                            {entry[0]}: {entry[1].total}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
              </>
            )}

            {/* Privacy Tab */}
            {settingsTab === "privacy" && (
              <div data-tutorial="settings-privacy">
            {/* FERPA Compliance & Data Privacy */}
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Shield"
                  size={20}
                  style={{ color: "#10b981" }}
                />
                Privacy & Data (FERPA)
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Graider is designed for FERPA compliance. Student names
                are sanitized before AI processing. Your data is stored
                securely on Graider's server and is never shared with
                third-party vendors or aggregated across districts.
              </p>

              {/* Privacy Features */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "15px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      PII Sanitization
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student names, IDs, emails, and phone numbers are
                    removed before AI processing
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No Third-Party Sharing
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student data is never sold, shared with vendors, or
                    aggregated across districts
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No AI Training
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    OpenAI and Anthropic APIs do not use submitted data
                    to train models (per their policies)
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      Audit Logging
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    All data access is logged for compliance
                    tracking and FERPA audit trails
                  </p>
                </div>
              </div>

              {/* Data Management Actions */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Data Management
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <button
                    onClick={async () => {
                      try {
                        const authHdrs = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/data-summary",
                          { headers: { ...authHdrs } },
                        );
                        const data = await response.json();
                        alert(
                          `Data Storage Summary\n\n` +
                            `• Grading Results: ${data.results.count} records\n` +
                            `• Settings: ${data.settings.exists ? "Saved" : "Not saved"}\n` +
                            `• Audit Log: ${data.audit_log.exists ? "Active" : "Not started"}\n\n` +
                            `Data Locations:\n` +
                            data.data_locations.join("\n"),
                        );
                      } catch (err) {
                        addToast(
                          "Failed to fetch data summary",
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Database" size={16} />
                    View Data Summary
                  </button>

                  <button
                    onClick={async () => {
                      try {
                        const authHdrs2 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/export-data",
                          { headers: { ...authHdrs2 } },
                        );
                        const data = await response.json();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `graider_export_${new Date().toISOString().split("T")[0]}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast("Failed to export data", "error");
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export All Data
                  </button>

                  {/* Export Individual Student Data */}
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <button
                      onClick={async () => {
                        if (exportStudentSearch.active) {
                          setExportStudentSearch({ active: false, query: "", results: [], allStudents: [] });
                          return;
                        }
                        // Load all students from all periods
                        let all = [];
                        try {
                          const results = await Promise.all(
                            periods.map((p) =>
                              api.getPeriodStudents(p.filename)
                                .then((d) => (d.students || []).map((s) => ({ ...s, period: p.period_name })))
                                .catch(() => [])
                            )
                          );
                          all = results.flat();
                        } catch (e) { /* ignore */ }
                        setExportStudentSearch({ active: true, query: "", results: [], allStudents: all });
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="UserCheck" size={16} />
                      Export Student Data
                    </button>
                    {exportStudentSearch.active && (
                      <div style={{ position: "absolute", top: "100%", left: 0, marginTop: "6px", zIndex: 100, width: "280px" }}>
                        <input
                          type="text"
                          placeholder="Type student name..."
                          value={exportStudentSearch.query}
                          onChange={(e) => {
                            const q = e.target.value;
                            const lq = q.toLowerCase().replace(/['"]/g, "");
                            const suggestions = lq.length >= 2 ? exportStudentSearch.allStudents.filter((s) => {
                              const full = (s.full || "").toLowerCase().replace(/['"]/g, "");
                              const first = (s.first || "").toLowerCase();
                              const last = (s.last || "").toLowerCase();
                              return full.includes(lq) || first.includes(lq) || last.includes(lq);
                            }).slice(0, 5) : [];
                            setExportStudentSearch(prev => ({ ...prev, query: q, results: suggestions }));
                          }}
                          style={{
                            width: "100%",
                            padding: "8px 12px",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                            background: "var(--modal-content-bg)",
                            color: "var(--text-primary)",
                            fontSize: "0.85rem",
                          }}
                          autoFocus
                        />
                        {exportStudentSearch.results.length > 0 && (
                          <div style={{
                            background: "var(--modal-content-bg)",
                            border: "1px solid var(--glass-border)",
                            borderRadius: "8px",
                            marginTop: "4px",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                            maxHeight: "200px",
                            overflowY: "auto",
                          }}>
                            {exportStudentSearch.results.map((student, idx) => (
                              <div
                                key={idx}
                                onClick={async () => {
                                  const name = student.full || (student.first + " " + student.last);
                                  setExportStudentSearch({ active: false, query: "", results: [] });
                                  try {
                                    const authH = await getAuthHeaders();
                                    const resp = await fetch("/api/ferpa/export-student", {
                                      method: "POST",
                                      headers: { "Content-Type": "application/json", ...authH },
                                      body: JSON.stringify({ student_name: name }),
                                    });
                                    const d = await resp.json();
                                    if (d.status === "success") {
                                      addToast("Exported " + d.record_count + " records for " + d.student_name, "success");
                                    } else {
                                      addToast("Export failed: " + (d.error || "Unknown error"), "error");
                                    }
                                  } catch (err) {
                                    addToast("Export failed: " + err.message, "error");
                                  }
                                }}
                                style={{
                                  padding: "10px 12px",
                                  cursor: "pointer",
                                  borderBottom: idx < exportStudentSearch.results.length - 1 ? "1px solid var(--glass-border)" : "none",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                }}
                                onMouseEnter={(e) => (e.target.style.background = "var(--glass-bg)")}
                                onMouseLeave={(e) => (e.target.style.background = "transparent")}
                              >
                                <Icon name="User" size={16} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                                <div>
                                  <div style={{ fontWeight: 500 }}>
                                    {student.full || (student.first + " " + student.last)}
                                  </div>
                                  {student.period && (
                                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                      {student.period}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Import Student Data */}
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <input
                      type="file"
                      accept=".json"
                      ref={importFileRef}
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const f = e.target.files[0];
                        if (!f) return;
                        e.target.value = "";
                        try {
                          const formData = new FormData();
                          formData.append("file", f);
                          formData.append("preview", "true");
                          const authH = await getAuthHeaders();
                          const resp = await fetch("/api/ferpa/import-student", {
                            method: "POST",
                            headers: { ...authH },
                            body: formData,
                          });
                          const d = await resp.json();
                          if (d.status === "preview") {
                            setImportStudentData({ active: true, preview: d, file: f, importing: false, selectedPeriod: "" });
                          } else {
                            addToast("Import failed: " + (d.error || "Unknown error"), "error");
                          }
                        } catch (err) {
                          addToast("Import failed: " + err.message, "error");
                        }
                      }}
                    />
                    <button
                      onClick={() => {
                        if (importStudentData.active) {
                          setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" });
                        } else {
                          importFileRef.current && importFileRef.current.click();
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="Upload" size={16} />
                      Import Student Data
                    </button>
                    {importStudentData.active && importStudentData.preview && (
                      <div style={{
                        position: "absolute", top: "100%", left: 0, marginTop: "6px", zIndex: 100, width: "320px",
                        background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)",
                        borderRadius: "8px", padding: "14px", boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                      }}>
                        <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                          Import {importStudentData.preview.student_name}?
                        </div>
                        <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "10px" }}>
                          {importStudentData.preview.detail_text}
                          {importStudentData.preview.original_period && (
                            <span> (from {importStudentData.preview.original_period})</span>
                          )}
                        </div>
                        {periods.length > 0 && (
                          <div style={{ marginBottom: "10px" }}>
                            <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                              Add to period:
                            </label>
                            <select
                              value={importStudentData.selectedPeriod}
                              onChange={(e) => setImportStudentData(prev => ({ ...prev, selectedPeriod: e.target.value }))}
                              style={{
                                width: "100%", padding: "6px 8px", borderRadius: "6px",
                                border: "1px solid var(--glass-border)", background: "var(--modal-content-bg)",
                                color: "var(--text-primary)", fontSize: "0.85rem",
                              }}
                            >
                              <option value="">No period (data only)</option>
                              {periods.map((p) => (
                                <option key={p.filename} value={p.filename}>{p.period_name}</option>
                              ))}
                            </select>
                          </div>
                        )}
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="btn btn-primary"
                            style={{ fontSize: "0.8rem", flex: 1 }}
                            disabled={importStudentData.importing}
                            onClick={async () => {
                              setImportStudentData(prev => ({ ...prev, importing: true }));
                              try {
                                const formData = new FormData();
                                formData.append("file", importStudentData.file);
                                if (importStudentData.selectedPeriod) {
                                  formData.append("period_filename", importStudentData.selectedPeriod);
                                }
                                const authH = await getAuthHeaders();
                                const resp = await fetch("/api/ferpa/import-student", {
                                  method: "POST",
                                  headers: { ...authH },
                                  body: formData,
                                });
                                const d = await resp.json();
                                if (d.status === "success") {
                                  const count = (d.imported_sections.results || 0);
                                  addToast("Imported " + (count ? count + " records" : "data") + " for " + d.student_name, "success");
                                  setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" });
                                } else {
                                  addToast("Import failed: " + (d.error || "Unknown error"), "error");
                                  setImportStudentData(prev => ({ ...prev, importing: false }));
                                }
                              } catch (err) {
                                addToast("Import failed: " + err.message, "error");
                                setImportStudentData(prev => ({ ...prev, importing: false }));
                              }
                            }}
                          >
                            {importStudentData.importing ? "Importing..." : "Confirm Import"}
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: "0.8rem" }}
                            onClick={() => setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" })}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={async () => {
                      if (
                        !confirm(
                          "⚠️ DELETE ALL STUDENT DATA?\n\n" +
                            "This will permanently delete:\n" +
                            "• All grading results\n" +
                            "• Current session data\n\n" +
                            "This action cannot be undone.\n\n" +
                            "Type 'DELETE' in the next prompt to confirm.",
                        )
                      )
                        return;

                      const confirmText = prompt(
                        "Type DELETE to confirm:",
                      );
                      if (confirmText !== "DELETE") {
                        addToast("Deletion cancelled", "warning");
                        return;
                      }

                      try {
                        const authHdrs3 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/delete-all-data",
                          {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                              ...authHdrs3,
                            },
                            body: JSON.stringify({ confirm: true }),
                          },
                        );
                        const data = await response.json();
                        if (data.status === "success") {
                          addToast(
                            "All student data has been deleted",
                            "success",
                          );
                          setTimeout(
                            () => window.location.reload(),
                            1000,
                          );
                        } else {
                          addToast(
                            "Error: " + (data.error || "Unknown error"),
                            "error",
                          );
                        }
                      } catch (err) {
                        addToast(
                          "Failed to delete data: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-danger"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Trash2" size={16} />
                    Delete All Data
                  </button>
                </div>
              </div>

              {/* Student Writing Profiles */}
              <div
                style={{
                  marginTop: "20px",
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    <Icon
                      name="UserCheck"
                      size={16}
                      style={{
                        marginRight: "8px",
                        verticalAlign: "middle",
                      }}
                    />
                    Student Writing Profiles
                  </div>
                  <button
                    onClick={async () => {
                      setStudentHistoryLoading(true);
                      try {
                        const data = await api.listStudentHistory();
                        setStudentHistoryList(data.students || []);
                      } catch (err) {
                        addToast(
                          "Failed to load history: " + err.message,
                          "error",
                        );
                      }
                      setStudentHistoryLoading(false);
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                  >
                    {studentHistoryLoading ? "Loading..." : "Refresh"}
                  </button>
                </div>
                <p
                  style={{
                    fontSize: "0.8rem",
                    color: "var(--text-muted)",
                    marginBottom: "12px",
                  }}
                >
                  Writing profiles track vocabulary complexity and style
                  patterns for AI detection. View or delete individual
                  profiles.
                </p>

                {studentHistoryList.length > 0 ? (
                  <>
                    <div
                      style={{
                        maxHeight: "200px",
                        overflowY: "auto",
                        marginBottom: "10px",
                      }}
                    >
                      {studentHistoryList.map((student) => (
                        <div
                          key={student.student_id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            padding: "8px 12px",
                            background: "var(--glass-bg)",
                            borderRadius: "6px",
                            marginBottom: "6px",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <div>
                            <div
                              style={{
                                fontWeight: 500,
                                fontSize: "0.85rem",
                              }}
                            >
                              {student.name || student.student_id}
                            </div>
                            <div
                              style={{
                                fontSize: "0.75rem",
                                color: "var(--text-muted)",
                              }}
                            >
                              {student.submissions_analyzed} submissions
                              • Complexity: {student.avg_complexity}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              onClick={async () => {
                                try {
                                  const data =
                                    await api.getStudentHistory(
                                      student.student_id,
                                    );
                                  setSelectedStudentHistory(data);
                                } catch (err) {
                                  addToast(
                                    "Failed to load: " + err.message,
                                    "error",
                                  );
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                fontSize: "0.75rem",
                              }}
                            >
                              <Icon name="Eye" size={12} />
                            </button>
                            <button
                              onClick={async () => {
                                if (
                                  !confirm(
                                    `Delete writing profile for ${student.name || student.student_id}?`,
                                  )
                                )
                                  return;
                                try {
                                  await api.deleteStudentHistory(
                                    student.student_id,
                                  );
                                  setStudentHistoryList((prev) =>
                                    prev.filter(
                                      (s) =>
                                        s.student_id !==
                                        student.student_id,
                                    ),
                                  );
                                  addToast("Profile deleted", "success");
                                } catch (err) {
                                  addToast(
                                    "Failed to delete: " + err.message,
                                    "error",
                                  );
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                fontSize: "0.75rem",
                                color: "#ef4444",
                              }}
                            >
                              <Icon name="Trash2" size={12} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={async () => {
                        if (
                          !confirm(
                            "Delete ALL student writing profiles? This resets AI detection baselines.",
                          )
                        )
                          return;
                        try {
                          const result =
                            await api.deleteAllStudentHistory();
                          setStudentHistoryList([]);
                          addToast(
                            `Deleted ${result.deleted} profiles`,
                            "success",
                          );
                        } catch (err) {
                          addToast(
                            "Failed to delete: " + err.message,
                            "error",
                          );
                        }
                      }}
                      className="btn btn-danger"
                      style={{ fontSize: "0.8rem" }}
                    >
                      <Icon name="Trash2" size={14} />
                      Delete All Profiles
                    </button>
                  </>
                ) : (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "var(--text-muted)",
                      fontSize: "0.85rem",
                    }}
                  >
                    {studentHistoryLoading
                      ? "Loading..."
                      : 'Click "Refresh" to load student writing profiles'}
                  </div>
                )}
              </div>

              {/* Trusted Writers */}
              <div
                style={{
                  marginTop: "20px",
                  padding: "15px",
                  background: "rgba(34,197,94,0.1)",
                  borderRadius: "12px",
                  border: "1px solid rgba(34,197,94,0.2)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "10px",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <Icon
                      name="ShieldCheck"
                      size={18}
                      style={{
                        color: "#22c55e",
                        verticalAlign: "middle",
                      }}
                    />
                    Trusted Writers
                  </div>
                  {(config.trustedStudents || []).length > 0 && (
                    <button
                      onClick={() => {
                        if (confirm("Remove all trusted writers?")) {
                          setConfig(prev => ({ ...prev, trustedStudents: [] }));
                          addToast("Cleared trusted writers list", "info");
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                    >
                      Clear All
                    </button>
                  )}
                </div>
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--text-muted)",
                    marginBottom: "12px",
                  }}
                >
                  Students marked as trusted writers won't be flagged for AI/copy detection.
                  Use this for students who naturally write well.
                </p>

                {(config.trustedStudents || []).length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    {config.trustedStudents.map((studentId) => {
                      const matchedResult = (status.results || []).find(r => (r.student_id || r.student) === studentId);
                      let displayName = matchedResult ? matchedResult.student_name : null;
                      if (!displayName) {
                        for (const p of periods) {
                          const s = (p.students || []).find(st => st.id === studentId || st.student_id === studentId);
                          if (s) { displayName = s.full || s.name || ((s.first || "") + " " + (s.last || "")).trim(); break; }
                        }
                      }
                      if (!displayName) displayName = studentId;
                      return (
                      <div
                        key={studentId}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "6px 10px",
                          background: "rgba(34,197,94,0.15)",
                          borderRadius: "6px",
                          fontSize: "0.85rem",
                        }}
                      >
                        <Icon name="User" size={14} style={{ color: "#22c55e" }} />
                        <span>{displayName}</span>
                        <button
                          onClick={() => {
                            setConfig(prev => ({
                              ...prev,
                              trustedStudents: prev.trustedStudents.filter(id => id !== studentId)
                            }));
                            addToast(`Removed ${displayName} from trusted list`, "info");
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: "2px",
                            color: "var(--text-muted)",
                          }}
                        >
                          <Icon name="X" size={12} />
                        </button>
                      </div>
                      );
                    })}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "15px",
                      textAlign: "center",
                      color: "var(--text-muted)",
                      fontSize: "0.85rem",
                      background: "rgba(0,0,0,0.1)",
                      borderRadius: "8px",
                    }}
                  >
                    No trusted writers yet. Mark students as trusted from the Results tab
                    when they're flagged for AI/copy detection.
                  </div>
                )}
              </div>

              {/* Student History Detail Modal */}
              {selectedStudentHistory && (
                <div
                  style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: "rgba(0,0,0,0.7)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 1000,
                  }}
                  onClick={() => setSelectedStudentHistory(null)}
                >
                  <div
                    style={{
                      background: "var(--card-bg)",
                      borderRadius: "12px",
                      padding: "25px",
                      maxWidth: "600px",
                      maxHeight: "80vh",
                      overflow: "auto",
                      width: "90%",
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "20px",
                      }}
                    >
                      <h3 style={{ margin: 0 }}>
                        <Icon
                          name="User"
                          size={20}
                          style={{ marginRight: "10px" }}
                        />
                        {selectedStudentHistory.name ||
                          selectedStudentHistory.student_id ||
                          "Student Profile"}
                      </h3>
                      <button
                        onClick={() => setSelectedStudentHistory(null)}
                        className="btn btn-secondary"
                        style={{ padding: "4px 8px" }}
                      >
                        <Icon name="X" size={16} />
                      </button>
                    </div>

                    <div
                      style={{
                        background: "var(--input-bg)",
                        borderRadius: "8px",
                        padding: "15px",
                        fontSize: "0.85rem",
                      }}
                    >
                      <pre
                        style={{
                          margin: 0,
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          fontFamily: "monospace",
                          fontSize: "0.8rem",
                        }}
                      >
                        {JSON.stringify(
                          selectedStudentHistory,
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
              </div>
            )}

            {/* Billing Tab */}
            {settingsTab === "billing" && (
              <>
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="CreditCard" size={20} style={{ color: "#6366f1" }} />
                    Subscription & Billing
                  </h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
                    Manage your Graider subscription plan and billing details.
                  </p>

                  {subscriptionLoading ? (
                    <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                      Loading subscription status...
                    </div>
                  ) : subscription && subscription.status === "active" ? (
                    <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", marginBottom: "20px", border: "1px solid var(--glass-border)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                        <span style={{ background: "#10b981", color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "0.75rem", fontWeight: 600 }}>Active</span>
                        <span style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                          {subscription.plan === "month" ? "Monthly" : subscription.plan === "year" ? "Annual" : subscription.plan} Plan
                        </span>
                      </div>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                        {subscription.cancel_at_period_end
                          ? "Cancels on: "
                          : "Renews on: "}
                        {new Date(subscription.current_period_end * 1000).toLocaleDateString()}
                      </p>
                      {subscription.cancel_at_period_end && (
                        <p style={{ fontSize: "0.8rem", color: "#f59e0b", marginTop: "8px" }}>
                          Your subscription will not renew. You can resubscribe anytime.
                        </p>
                      )}
                      <button
                        onClick={async () => {
                          try {
                            const res = await api.createPortalSession();
                            if (res.portal_url) window.location.href = res.portal_url;
                            else addToast(res.error || "Failed to open portal", "error");
                          } catch { addToast("Failed to open billing portal", "error"); }
                        }}
                        style={{ marginTop: "16px", padding: "10px 20px", borderRadius: "8px", border: "none", background: "var(--accent-primary)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
                      >
                        Manage Subscription
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", marginBottom: "20px", border: "1px solid var(--glass-border)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                          <span style={{ background: "var(--text-secondary)", color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "0.75rem", fontWeight: 600 }}>No Active Plan</span>
                        </div>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Subscribe to unlock all Graider features.
                        </p>
                        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                          <button
                            onClick={async () => {
                              try {
                                const res = await api.createCheckoutSession("monthly");
                                if (res.checkout_url) window.location.href = res.checkout_url;
                                else addToast(res.error || "Failed to start checkout", "error");
                              } catch { addToast("Failed to start checkout", "error"); }
                            }}
                            style={{ padding: "10px 20px", borderRadius: "8px", border: "1px solid var(--accent-primary)", background: "transparent", color: "var(--accent-primary)", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
                          >
                            Subscribe Monthly
                          </button>
                          <button
                            onClick={async () => {
                              try {
                                const res = await api.createCheckoutSession("annual");
                                if (res.checkout_url) window.location.href = res.checkout_url;
                                else addToast(res.error || "Failed to start checkout", "error");
                              } catch { addToast("Failed to start checkout", "error"); }
                            }}
                            style={{ padding: "10px 20px", borderRadius: "8px", border: "none", background: "var(--accent-primary)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
                          >
                            Subscribe Annual
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => {
                      setSubscriptionLoading(true);
                      api.getSubscriptionStatus()
                        .then((res) => { if (!res.error) setSubscription(res); })
                        .catch(() => {})
                        .finally(() => setSubscriptionLoading(false));
                    }}
                    style={{ padding: "8px 16px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.8rem" }}
                  >
                    Refresh Status
                  </button>
                </div>

                {/* API Cost Controls */}
                <div style={{ marginTop: "30px" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="Shield" size={20} style={{ color: "#f59e0b" }} />
                    API Cost Controls
                  </h3>
                  <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", border: "1px solid var(--glass-border)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                      <div>
                        <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Max cost per grading session ($)</label>
                        <input
                          type="number"
                          className="input"
                          placeholder="e.g. 2.00"
                          min="0"
                          step="0.01"
                          value={config.cost_limit_per_session || ""}
                          onChange={(e) => setConfig((prev) => ({ ...prev, cost_limit_per_session: parseFloat(e.target.value) || 0 }))}
                          style={{ width: "100%" }}
                        />
                      </div>
                      <div>
                        <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Monthly API budget ($)</label>
                        <input
                          type="number"
                          className="input"
                          placeholder="e.g. 25.00"
                          min="0"
                          step="0.01"
                          value={config.cost_limit_monthly || ""}
                          onChange={(e) => setConfig((prev) => ({ ...prev, cost_limit_monthly: parseFloat(e.target.value) || 0 }))}
                          style={{ width: "100%" }}
                        />
                      </div>
                    </div>
                    <div style={{ marginBottom: "12px" }}>
                      <label className="label" style={{ fontSize: "0.8rem", marginBottom: "6px" }}>Warning threshold</label>
                      <select
                        className="input"
                        value={config.cost_warning_pct || 80}
                        onChange={(e) => setConfig((prev) => ({ ...prev, cost_warning_pct: parseInt(e.target.value) }))}
                        style={{ width: "auto", cursor: "pointer" }}
                      >
                        <option value={50}>50%</option>
                        <option value={60}>60%</option>
                        <option value={70}>70%</option>
                        <option value={80}>80%</option>
                        <option value={90}>90%</option>
                      </select>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Set to 0 for no limit. Session limit auto-stops grading when reached.
                    </p>
                  </div>
                </div>

                {/* Unified Cost Summary */}
                <div style={{ marginTop: "30px" }}>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon name="BarChart3" size={20} style={{ color: "#10b981" }} />
                    API Usage Summary
                  </h3>
                  {!costSummary ? (
                    <button
                      onClick={async () => {
                        try {
                          const [analyticsRes, plannerRes, assistantRes] = await Promise.all([
                            api.getAnalytics().catch(() => null),
                            api.getPlannerCosts().catch(() => null),
                            api.getAssistantCosts().catch(() => null),
                          ]);
                          setCostSummary({
                            grading: analyticsRes?.cost_summary || { total_cost: 0, total_graded: 0, avg_cost_per_student: 0 },
                            planner: plannerRes?.total || { total_cost: 0, api_calls: 0 },
                            assistant: assistantRes?.total || { total_cost: 0, api_calls: 0 },
                          });
                        } catch {
                          setCostSummary({ grading: { total_cost: 0 }, planner: { total_cost: 0 }, assistant: { total_cost: 0 } });
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="RefreshCw" size={14} />
                      Load Cost Summary
                    </button>
                  ) : (
                    <div style={{ background: "var(--input-bg)", borderRadius: "12px", padding: "20px", border: "1px solid var(--glass-border)" }}>
                      <div style={{ display: "grid", gap: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Grading</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.grading.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.grading.total_graded || 0} students</span>
                            <span>~${(costSummary.grading.avg_cost_per_student || 0).toFixed(4)}/student</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Assistant</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.assistant.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.assistant.api_calls || 0} API calls</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Planner</span>
                          <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            <span>${(costSummary.planner.total_cost || 0).toFixed(4)}</span>
                            <span>{costSummary.planner.api_calls || 0} API calls</span>
                          </div>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 0", fontWeight: 700 }}>
                          <span style={{ fontSize: "0.9rem" }}>Total</span>
                          <span style={{ fontSize: "0.9rem", color: "#f59e0b" }}>
                            ${((costSummary.grading.total_cost || 0) + (costSummary.assistant.total_cost || 0) + (costSummary.planner.total_cost || 0)).toFixed(4)}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={async () => {
                          try {
                            const [analyticsRes, plannerRes, assistantRes] = await Promise.all([
                              api.getAnalytics().catch(() => null),
                              api.getPlannerCosts().catch(() => null),
                              api.getAssistantCosts().catch(() => null),
                            ]);
                            setCostSummary({
                              grading: analyticsRes?.cost_summary || { total_cost: 0, total_graded: 0, avg_cost_per_student: 0 },
                              planner: plannerRes?.total || { total_cost: 0, api_calls: 0 },
                              assistant: assistantRes?.total || { total_cost: 0, api_calls: 0 },
                            });
                          } catch { /* ignore */ }
                        }}
                        style={{ marginTop: "12px", padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.75rem" }}
                      >
                        Refresh
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Resources Tab */}
            {settingsTab === "resources" && (
              <div data-tutorial="resources-upload">
                <p
                  style={{
                    fontSize: "0.9rem",
                    color: "var(--text-secondary)",
                    marginBottom: "25px",
                  }}
                >
                  Upload curriculum guides, rubrics, standards documents, and
                  other reference materials to enhance AI grading and lesson
                  planning.
                </p>

                {/* Supporting Documents Section */}
                <div>
                  <h3
                    style={{
                      fontSize: "1.1rem",
                      fontWeight: 700,
                      marginBottom: "15px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Icon
                      name="FileText"
                      size={20}
                      style={{ color: "#10b981" }}
                    />
                    Supporting Documents
                  </h3>
                  <p
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      marginBottom: "15px",
                    }}
                  >
                    Upload curriculum guides, rubrics, standards docs, or
                    other reference materials
                  </p>

                  <input
                    ref={supportDocInputRef}
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.md"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setUploadingDoc(true);
                      try {
                        const result = await api.uploadSupportDocument(
                          file,
                          newDocType,
                          newDocDescription,
                        );
                        if (result.error) {
                          addToast(result.error, "error");
                        } else {
                          const docsData = await api.listSupportDocuments();
                          setSupportDocs(docsData.documents || []);
                          setNewDocDescription("");
                        }
                      } catch (err) {
                        addToast("Upload failed: " + err.message, "error");
                      }
                      setUploadingDoc(false);
                      e.target.value = "";
                    }}
                  />

                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "15px",
                      flexWrap: "wrap",
                    }}
                  >
                    <select
                      className="input"
                      value={newDocType}
                      onChange={(e) => setNewDocType(e.target.value)}
                      style={{ maxWidth: "180px" }}
                    >
                      <option value="curriculum">Curriculum Guide</option>
                      <option value="rubric">Rubric Template</option>
                      <option value="standards">Standards Document</option>
                      <option value="general">General Reference</option>
                    </select>
                    <input
                      type="text"
                      className="input"
                      placeholder="Description (optional)"
                      value={newDocDescription}
                      onChange={(e) => setNewDocDescription(e.target.value)}
                      style={{ flex: 1, minWidth: "200px" }}
                    />
                    <button
                      onClick={() => supportDocInputRef.current?.click()}
                      className="btn btn-secondary"
                      disabled={uploadingDoc}
                    >
                      <Icon name="Upload" size={18} />
                      {uploadingDoc ? "Uploading..." : "Upload Document"}
                    </button>
                  </div>

                  {supportDocs.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                      }}
                    >
                      {supportDocs.map((doc) => (
                        <div
                          key={doc.filename}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "12px 15px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "12px",
                            }}
                          >
                            <Icon
                              name={
                                doc.doc_type === "rubric"
                                  ? "ClipboardCheck"
                                  : doc.doc_type === "standards"
                                    ? "BookOpen"
                                    : "FileText"
                              }
                              size={18}
                              style={{ color: "#10b981" }}
                            />
                            <div>
                              <div style={{ fontWeight: 600 }}>
                                {doc.filename}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.8rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                {doc.doc_type}{" "}
                                {doc.description && `• ${doc.description}`}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={async () => {
                              if (confirm("Delete this document?")) {
                                await api.deleteSupportDocument(doc.filename);
                                const data = await api.listSupportDocuments();
                                setSupportDocs(data.documents || []);
                              }
                            }}
                            style={{
                              padding: "6px 10px",
                              background: "rgba(239,68,68,0.2)",
                              border: "none",
                              borderRadius: "6px",
                              color: "#ef4444",
                              cursor: "pointer",
                            }}
                          >
                            <Icon name="Trash2" size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

      {/* Roster Column Mapping Modal */}
      {rosterMappingModal.show && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "500px",
              maxHeight: "80vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                Map Roster Columns
              </h3>
              <button
                onClick={() =>
                  setRosterMappingModal({ show: false, roster: null })
                }
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p
              style={{
                fontSize: "0.9rem",
                color: "var(--text-secondary)",
                marginBottom: "20px",
              }}
            >
              Map your CSV columns to the required fields
            </p>

            {[
              "student_id",
              "student_name",
              "first_name",
              "last_name",
              "student_email",
              "parent_email",
            ].map((field) => (
              <div key={field} style={{ marginBottom: "15px" }}>
                <label
                  className="label"
                  style={{ textTransform: "capitalize" }}
                >
                  {field.replace(/_/g, " ")}
                </label>
                <select
                  className="input"
                  value={
                    rosterMappingModal.roster?.column_mapping?.[
                      field
                    ] || ""
                  }
                  onChange={(e) => {
                    const newMapping = {
                      ...rosterMappingModal.roster?.column_mapping,
                      [field]: e.target.value,
                    };
                    setRosterMappingModal((prev) => ({
                      ...prev,
                      roster: {
                        ...prev.roster,
                        column_mapping: newMapping,
                      },
                    }));
                  }}
                >
                  <option value="">-- Select Column --</option>
                  {(rosterMappingModal.roster?.headers || []).map(
                    (header) => (
                      <option key={header} value={header}>
                        {header}
                      </option>
                    ),
                  )}
                </select>
              </div>
            ))}

            <div
              style={{
                display: "flex",
                gap: "10px",
                marginTop: "20px",
              }}
            >
              <button
                onClick={async () => {
                  try {
                    await api.saveRosterMapping(
                      rosterMappingModal.roster.filename,
                      rosterMappingModal.roster.column_mapping,
                    );
                    const data = await api.listRosters();
                    setRosters(data.rosters || []);
                    setRosterMappingModal({
                      show: false,
                      roster: null,
                    });
                  } catch (err) {
                    addToast(
                      "Error saving mapping: " + err.message,
                      "error",
                    );
                  }
                }}
                className="btn btn-primary"
              >
                <Icon name="Save" size={18} />
                Save Mapping
              </button>
              <button
                onClick={() =>
                  setRosterMappingModal({ show: false, roster: null })
                }
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Parent Contact Column Mapping Modal */}
      {parentContactMapping.show && parentContactMapping.preview && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "560px",
              maxHeight: "85vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                Map Parent Contact Columns
              </h3>
              <button
                onClick={() => setParentContactMapping({ show: false, preview: null, mapping: null })}
                style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer" }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
              {parentContactMapping.preview.sheets.length > 1
                ? parentContactMapping.preview.sheets.length + " sheets detected (each sheet = one period)"
                : parentContactMapping.preview.sheets[0].row_count + " rows detected"}
            </p>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "20px" }}>
              Graider auto-detects emails (contains @) and phone numbers in the selected contact columns.
            </p>

            {/* Name Column */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Student Name Column</label>
              <select
                className="input"
                value={parentContactMapping.mapping?.name_col || ""}
                onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { name_col: e.target.value }) }); }); }}
              >
                <option value="">-- Select Column --</option>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  return <option key={h} value={h}>{h}</option>;
                })}
              </select>
            </div>

            {/* Name Format */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Name Format</label>
              <div style={{ display: "flex", gap: "15px", marginTop: "4px" }}>
                {[
                  { value: "last_first", label: "Last, First" },
                  { value: "first_last", label: "First Last" },
                  { value: "single", label: "Single name" },
                ].map(function(opt) {
                  return (
                    <label key={opt.value} style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input
                        type="radio"
                        name="pcNameFormat"
                        checked={parentContactMapping.mapping?.name_format === opt.value}
                        onChange={function() { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { name_format: opt.value }) }); }); }}
                      />
                      {opt.label}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Student ID Column */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Student ID Column (optional)</label>
              <select
                className="input"
                value={parentContactMapping.mapping?.id_col || ""}
                onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { id_col: e.target.value }) }); }); }}
              >
                <option value="">-- None --</option>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  return <option key={h} value={h}>{h}</option>;
                })}
              </select>
            </div>

            {/* Strip Digits */}
            {parentContactMapping.mapping?.id_col && (
              <div style={{ marginBottom: "15px" }}>
                <label className="label">Strip last N digits from Student ID (grade code)</label>
                <input
                  type="number"
                  className="input"
                  min="0"
                  max="4"
                  value={parentContactMapping.mapping?.id_strip_digits || 0}
                  onChange={function(e) {
                    var val = Math.max(0, Math.min(4, parseInt(e.target.value) || 0));
                    setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { id_strip_digits: val }) }); });
                  }}
                  style={{ width: "80px" }}
                />
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  Set to 2 if IDs have a 2-digit grade suffix (e.g., 12345678906 becomes 123456789)
                </p>
              </div>
            )}

            {/* Contact Columns */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Contact Columns (email and phone)</label>
              <div style={{ maxHeight: "150px", overflow: "auto", padding: "8px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  var isChecked = (parentContactMapping.mapping?.contact_cols || []).indexOf(h) !== -1;
                  return (
                    <label key={h} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 0", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={function() {
                          setParentContactMapping(function(prev) {
                            var cols = prev.mapping?.contact_cols || [];
                            var updated = isChecked ? cols.filter(function(c) { return c !== h; }) : cols.concat([h]);
                            return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { contact_cols: updated }) });
                          });
                        }}
                      />
                      {h}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Period Column (only for single-sheet files) */}
            {parentContactMapping.preview.sheets.length === 1 && (
              <div style={{ marginBottom: "15px" }}>
                <label className="label">Period Column (optional)</label>
                <select
                  className="input"
                  value={parentContactMapping.mapping?.period_col || ""}
                  onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { period_col: e.target.value }) }); }); }}
                >
                  <option value="">-- None --</option>
                  {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                    return <option key={h} value={h}>{h}</option>;
                  })}
                </select>
              </div>
            )}

            {parentContactMapping.preview.sheets.length > 1 && (
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "15px", fontStyle: "italic" }}>
                Period will be set from sheet names: {parentContactMapping.preview.sheets.map(function(s) { return s.name; }).join(", ")}
              </p>
            )}

            {/* Action Buttons */}
            <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
              <button
                onClick={async function() {
                  if (!parentContactMapping.mapping?.name_col) {
                    addToast("Please select a name column", "error");
                    return;
                  }
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.saveParentContactMapping(parentContactMapping.mapping);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      addToast(
                        "Imported " + result.unique_students + " students (" + result.with_email + " with email)",
                        "success"
                      );
                      var contactsData = await api.getParentContacts();
                      setParentContacts(contactsData);
                      setParentContactMapping({ show: false, preview: null, mapping: null });
                    }
                  } catch (err) {
                    addToast("Import failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                }}
                className="btn btn-primary"
                disabled={uploadingParentContacts}
              >
                <Icon name="Save" size={18} />
                {uploadingParentContacts ? "Importing..." : "Save & Import"}
              </button>
              <button
                onClick={function() { setParentContactMapping({ show: false, preview: null, mapping: null }); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Student from Screenshot Modal */}
      {addStudentModal.show && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "600px",
              maxHeight: "90vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name="UserPlus" size={24} style={{ color: "#8b5cf6" }} />
                Add Student to Roster
              </h3>
              <button
                onClick={() => setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null })}
                style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer" }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            {addStudentModal.loading && (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <div style={{ marginBottom: "15px", color: "var(--text-secondary)" }}>
                  <Icon name="Loader2" size={32} style={{ animation: "spin 1s linear infinite" }} />
                </div>
                <p>Extracting student info with AI...</p>
              </div>
            )}

            {addStudentModal.error && (
              <div style={{ padding: "20px", background: "rgba(239,68,68,0.1)", borderRadius: "8px", marginBottom: "20px" }}>
                <p style={{ color: "#ef4444", fontWeight: 600 }}>Error: {addStudentModal.error}</p>
              </div>
            )}

            {addStudentModal.student && !addStudentModal.loading && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px", marginBottom: "20px" }}>
                  <div>
                    <label className="label">First Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.first_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, first_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Middle Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.middle_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, middle_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Last Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.last_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, last_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Student ID</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.student_id || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, student_id: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Email</label>
                    <input
                      type="email"
                      className="input"
                      value={addStudentModal.student.email || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, email: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Period *</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="e.g., 2"
                      value={addStudentModal.student.period || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, period: e.target.value } }))}
                    />
                  </div>
                </div>

                {addStudentModal.image && (
                  <div style={{ marginBottom: "20px" }}>
                    <label className="label">Source Image</label>
                    <img
                      src={addStudentModal.image}
                      alt="Student info screenshot"
                      style={{ maxWidth: "100%", maxHeight: "200px", borderRadius: "8px", border: "1px solid var(--glass-border)" }}
                    />
                  </div>
                )}

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null })}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={async () => {
                      if (!addStudentModal.student.period) {
                        addToast("Please enter a period", "warning");
                        return;
                      }
                      try {
                        const authHdrs = await getAuthHeaders();
                        const response = await fetch("/api/add-student-to-roster", {
                          method: "POST",
                          headers: { "Content-Type": "application/json", ...authHdrs },
                          body: JSON.stringify({ student: addStudentModal.student, period: addStudentModal.student.period }),
                        });
                        const data = await response.json();
                        if (data.error) {
                          addToast(data.error, "error");
                        } else {
                          addToast(data.message, "success");
                          setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null });
                        }
                      } catch (err) {
                        addToast("Failed to add student: " + err.message, "error");
                      }
                    }}
                    className="btn btn-primary"
                  >
                    <Icon name="UserPlus" size={18} />
                    Add to Period {addStudentModal.student.period || "?"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Accommodation Assignment Modal */}
      {accommodationModal.show && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "500px",
              maxHeight: "80vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Heart"
                  size={22}
                  style={{ color: "#f472b6" }}
                />
                {accommodationModal.studentId
                  ? "Edit Accommodations"
                  : "Add Student Accommodations"}
              </h3>
              <button
                onClick={() => {
                  setAccommodationModal({
                    show: false,
                    studentId: null,
                  });
                  setSelectedAccommodationPresets([]);
                  setAccommodationCustomNotes("");
                  setAccommEllLanguage("");
                  setAccommSelectedStudents({});

                  setAccommPeriodFilter("");
                  setAccommStudentsList([]);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p
              style={{
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
                marginBottom: "20px",
                padding: "10px",
                background: "rgba(74, 222, 128, 0.1)",
                borderRadius: "8px",
                border: "1px solid rgba(74, 222, 128, 0.2)",
              }}
            >
              <Icon
                name="Shield"
                size={14}
                style={{ color: "#4ade80", marginRight: "6px" }}
              />
              FERPA Compliant: Only accommodation types are sent to AI,
              never student names or IDs.
            </p>

            {/* Student Selection (for new students) */}
            {!accommodationModal.studentId && (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">Select Students</label>
                {/* Period selector */}
                <select
                  className="input"
                  value={accommPeriodFilter}
                  onChange={async (e) => {
                    const val = e.target.value;
                    setAccommPeriodFilter(val);
                    setAccommSelectedStudents({});
                    if (val) {
                      try {
                        const data =
                          await api.getPeriodStudents(val);
                        if (data.students)
                          setAccommStudentsList(data.students);
                      } catch (err) {
                        setAccommStudentsList([]);
                      }
                    } else {
                      setAccommStudentsList([]);
                    }
                  }}
                  style={{ marginBottom: "8px" }}
                >
                  <option value="">Choose a period...</option>
                  {sortedPeriods.map((p) => (
                    <option key={p.filename} value={p.filename}>
                      {p.period_name} ({p.student_count} students)
                    </option>
                  ))}
                </select>
                {/* Student checkbox list */}
                {accommStudentsList.length > 0 && (
                  <div
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                      border: "1px solid var(--input-border)",
                      borderRadius: "8px",
                    }}
                  >
                    {accommStudentsList.map((s) => {
                      const sid = s.id || s.student_id || "";
                      const name = (
                        s.full ||
                        (s.first || "") + " " + (s.last || "")
                      ).trim();
                      const checked = !!accommSelectedStudents[sid];
                      return (
                        <label
                          key={sid}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            padding: "8px 12px",
                            borderBottom:
                              "1px solid var(--input-border)",
                            cursor: "pointer",
                            background: checked
                              ? "rgba(96,165,250,0.1)"
                              : "transparent",
                            fontSize: "0.85rem",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              setAccommSelectedStudents((prev) => {
                                const next = { ...prev };
                                if (e.target.checked) {
                                  next[sid] = name;
                                } else {
                                  delete next[sid];
                                }
                                return next;
                              });
                            }}
                          />
                          {name}
                        </label>
                      );
                    })}
                  </div>
                )}
                {Object.keys(accommSelectedStudents).length > 0 && (
                  <div
                    style={{
                      marginTop: "6px",
                      fontSize: "0.8rem",
                      color: "#60a5fa",
                    }}
                  >
                    {Object.keys(accommSelectedStudents).length}{" "}
                    student(s) selected
                  </div>
                )}
              </div>
            )}

            {/* Preset Selection */}
            <div style={{ marginBottom: "20px" }}>
              <label className="label">
                Select Accommodation Presets
              </label>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  maxHeight: "200px",
                  overflowY: "auto",
                }}
              >
                {accommodationPresets.map((preset) => (
                  <label
                    key={preset.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      padding: "10px",
                      background: selectedAccommodationPresets.includes(
                        preset.id,
                      )
                        ? "rgba(244, 114, 182, 0.15)"
                        : "var(--input-bg)",
                      borderRadius: "8px",
                      border: selectedAccommodationPresets.includes(
                        preset.id,
                      )
                        ? "1px solid rgba(244, 114, 182, 0.4)"
                        : "1px solid var(--input-border)",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedAccommodationPresets.includes(
                        preset.id,
                      )}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedAccommodationPresets([
                            ...selectedAccommodationPresets,
                            preset.id,
                          ]);
                        } else {
                          setSelectedAccommodationPresets(
                            selectedAccommodationPresets.filter(
                              (id) => id !== preset.id,
                            ),
                          );
                        }
                      }}
                      style={{ marginTop: "2px" }}
                    />
                    <div>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: "0.85rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <Icon
                          name={preset.icon || "FileText"}
                          size={14}
                          style={{ color: "#f472b6" }}
                        />
                        {preset.name}
                      </div>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          marginTop: "2px",
                        }}
                      >
                        {preset.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* ELL Language selector — shown when ELL Support preset is selected */}
            {selectedAccommodationPresets.includes("ell_support") && (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">
                  Home Language (for bilingual feedback)
                </label>
                <select
                  className="input"
                  value={accommEllLanguage}
                  onChange={(e) =>
                    setAccommEllLanguage(e.target.value)
                  }
                >
                  <option value="">English only (no translation)</option>
                  <option value="spanish">Spanish</option>
                  <option value="portuguese">Portuguese</option>
                  <option value="haitian creole">Haitian Creole</option>
                  <option value="french">French</option>
                  <option value="arabic">Arabic</option>
                  <option value="chinese (simplified)">Chinese (Simplified)</option>
                  <option value="chinese (traditional)">Chinese (Traditional)</option>
                  <option value="vietnamese">Vietnamese</option>
                  <option value="korean">Korean</option>
                  <option value="tagalog">Tagalog</option>
                  <option value="russian">Russian</option>
                  <option value="hindi">Hindi</option>
                  <option value="urdu">Urdu</option>
                  <option value="bengali">Bengali</option>
                  <option value="japanese">Japanese</option>
                  <option value="german">German</option>
                  <option value="italian">Italian</option>
                  <option value="polish">Polish</option>
                  <option value="somali">Somali</option>
                  <option value="swahili">Swahili</option>
                  <option value="burmese">Burmese</option>
                  <option value="nepali">Nepali</option>
                  <option value="gujarati">Gujarati</option>
                  <option value="amharic">Amharic</option>
                </select>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginTop: "6px",
                  }}
                >
                  If set, feedback will be provided in both English and
                  the selected language.
                </p>
              </div>
            )}

            {/* Custom Notes */}
            <div style={{ marginBottom: "20px" }}>
              <label className="label">
                Additional Notes (Optional)
              </label>
              <textarea
                className="input"
                value={accommodationCustomNotes}
                onChange={(e) =>
                  setAccommodationCustomNotes(e.target.value)
                }
                placeholder="Any additional accommodation instructions..."
                style={{ minHeight: "80px", resize: "vertical" }}
              />
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  marginTop: "6px",
                }}
              >
                These notes will be included in AI grading instructions
                (without student identity).
              </p>
            </div>

            {/* Actions */}
            <div
              style={{
                display: "flex",
                gap: "10px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={async () => {
                  // Single edit mode vs multi-select mode
                  const studentIds = accommodationModal.studentId
                    ? [accommodationModal.studentId]
                    : Object.keys(accommSelectedStudents);

                  if (studentIds.length === 0) {
                    addToast(
                      "Please select at least one student",
                      "warning",
                    );
                    return;
                  }

                  if (
                    selectedAccommodationPresets.length === 0 &&
                    !accommodationCustomNotes
                  ) {
                    addToast(
                      "Please select at least one preset or add custom notes",
                      "warning",
                    );
                    return;
                  }

                  try {
                    // Save accommodation for each selected student
                    for (const sid of studentIds) {
                      const name =
                        accommSelectedStudents[sid] || "";
                      await api.setStudentAccommodation(
                        sid,
                        selectedAccommodationPresets,
                        accommodationCustomNotes,
                        name,
                      );
                    }

                    // Save ELL language if ELL Support selected
                    if (
                      selectedAccommodationPresets.includes(
                        "ell_support",
                      ) &&
                      accommEllLanguage
                    ) {
                      try {
                        const existing =
                          await api.getEllStudents();
                        const ellData =
                          existing && typeof existing === "object"
                            ? existing
                            : {};
                        for (const sid of studentIds) {
                          ellData[sid] = {
                            student_name:
                              accommSelectedStudents[sid] || sid,
                            language: accommEllLanguage,
                          };
                        }
                        await api.saveEllStudents(ellData);
                      } catch (ellErr) {
                        // Non-blocking
                      }
                    }

                    // If editing single student & ELL Support removed, clear ELL entry
                    if (
                      accommodationModal.studentId &&
                      !selectedAccommodationPresets.includes(
                        "ell_support",
                      )
                    ) {
                      try {
                        const existing =
                          await api.getEllStudents();
                        if (
                          existing &&
                          existing[accommodationModal.studentId]
                        ) {
                          delete existing[
                            accommodationModal.studentId
                          ];
                          await api.saveEllStudents(existing);
                        }
                      } catch (ellErr) {
                        // Non-blocking
                      }
                    }

                    // Reload accommodations
                    const data = await api.getStudentAccommodations();
                    if (data.accommodations)
                      setStudentAccommodations(data.accommodations);

                    addToast(
                      studentIds.length +
                        " student(s) updated",
                      "success",
                    );
                    setAccommodationModal({
                      show: false,
                      studentId: null,
                    });
                    setSelectedAccommodationPresets([]);
                    setAccommodationCustomNotes("");
                    setAccommEllLanguage("");
                    setAccommSelectedStudents({});
                    setAccommPeriodFilter("");
                    setAccommStudentsList([]);
                  } catch (err) {
                    addToast(
                      "Error saving accommodation: " + err.message,
                      "error",
                    );
                  }
                }}
                className="btn btn-primary"
              >
                <Icon name="Save" size={18} />
                Save Accommodations
              </button>
              <button
                onClick={() => {
                  setAccommodationModal({
                    show: false,
                    studentId: null,
                  });
                  setSelectedAccommodationPresets([]);
                  setAccommodationCustomNotes("");
                  setAccommEllLanguage("");
                  setAccommSelectedStudents({});

                  setAccommPeriodFilter("");
                  setAccommStudentsList([]);
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
