import React, { useRef, useState, useEffect } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";
import { getAuthHeaders } from "../services/api";
import SettingsGeneral from "../components/SettingsGeneral";
import SettingsGrading from "../components/SettingsGrading";
import SettingsBilling from "../components/SettingsBilling";
import SettingsAI from "../components/SettingsAI";
import SettingsPrivacy from "../components/SettingsPrivacy";
import SettingsResources from "../components/SettingsResources";
import SettingsClassroom from "../components/SettingsClassroom";

export default React.memo(function SettingsTab({
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
  // PR 4 of the Grade tab extraction sprint deleted the dead pass-through of
  // loadAvailableFiles + filesLoading from App.jsx. Both were unused inside
  // SettingsTab body — the function was a no-op and the bool was never read.
  sortedPeriods,
  accommodationPresets,
  EDTECH_TOOLS,
  MODEL_COST_PER_ASSIGNMENT,
  addToast,
}) {
  const periodInputRef = useRef(null);
  const parentContactsInputRef = useRef(null);
  const supportDocInputRef = useRef(null);
  const importFileRef = useRef(null);
  const [showVportalPassword, setShowVportalPassword] = useState(false);

  // Clever integration state
  const isCleverUser = !!(window.__graiderUser && window.__graiderUser.id && window.__graiderUser.id.startsWith('clever:'));
  const [cleverSyncing, setCleverSyncing] = useState(false);
  const [cleverSyncResult, setCleverSyncResult] = useState(null);
  const [cleverSelectedSections, setCleverSelectedSections] = useState({});
  const [cleverAccommSuggestions, setCleverAccommSuggestions] = useState(null);
  const [cleverApplying, setCleverApplying] = useState(false);
  const [showManualSetup, setShowManualSetup] = useState(false);
  const [availableStates, setAvailableStates] = useState([]);

  // OneRoster integration state
  var [oneRosterConfig, setOneRosterConfig] = useState({
    base_url: '', client_id: '', client_secret: '', token_url: '',
    school_id: '', teacher_sourced_id: '',
  });
  var [oneRosterStatus, setOneRosterStatus] = useState(null);
  var [oneRosterSyncing, setOneRosterSyncing] = useState(false);
  var [oneRosterAccommodations, setOneRosterAccommodations] = useState(null);
  var [oneRosterTestResult, setOneRosterTestResult] = useState(null);
  var [oneRosterSaving, setOneRosterSaving] = useState(false);
  var [oneRosterApplying, setOneRosterApplying] = useState(false);
  var [oneRosterSyncResult, setOneRosterSyncResult] = useState(null);
  var [showOneRosterSecret, setShowOneRosterSecret] = useState(false);
  var [oneRosterHasCredentials, setOneRosterHasCredentials] = useState(false);
  var [districtSisProvider, setDistrictSisProvider] = useState(null);
  var [teacherSisId, setTeacherSisId] = useState('');

  // LTI 1.3 integration state
  var [ltiPlatforms, setLtiPlatforms] = useState([]);
  var [ltiToolConfig, setLtiToolConfig] = useState(null);
  var [ltiNewPlatform, setLtiNewPlatform] = useState({
    name: '', issuer: '', client_id: '', auth_login_url: '',
    auth_token_url: '', jwks_url: '', deployment_ids: '',
  });
  var [ltiSaving, setLtiSaving] = useState(false);
  var [ltiShowForm, setLtiShowForm] = useState(false);
  var [ltiContexts, setLtiContexts] = useState([]);
  var [ltiSelectedContext, setLtiSelectedContext] = useState(null);
  var [ltiSyncLabel, setLtiSyncLabel] = useState('');
  var [ltiSyncMaxScore, setLtiSyncMaxScore] = useState(100);
  var [ltiSyncScores, setLtiSyncScores] = useState([]);
  var [ltiSyncing, setLtiSyncing] = useState(false);
  var [ltiSyncResult, setLtiSyncResult] = useState(null);

  // Admin access state
  var [adminClaimCode, setAdminClaimCode] = useState('');
  var [adminClaimResult, setAdminClaimResult] = useState(null);
  var [adminStatus, setAdminStatus] = useState(null);

  // Provider detection
  var activeProvider = null;
  if (isCleverUser) {
    activeProvider = 'clever';
  } else if (oneRosterStatus === 'connected') {
    activeProvider = 'oneroster';
  }

  useEffect(() => {
    api.getAvailableStates().then((data) => {
      if (data.states) setAvailableStates(data.states);
    }).catch(() => {});
    // Load OneRoster config on mount
    api.getOneRosterConfig().then(function(data) {
      if (data.config) {
        setOneRosterConfig(function(prev) {
          return Object.assign({}, prev, {
            base_url: data.config.base_url || '',
            client_id: data.config.client_id || '',
            client_secret: '',
            token_url: data.config.token_url || '',
            school_id: data.config.school_id || '',
            teacher_sourced_id: data.config.teacher_sourced_id || '',
          });
        });
        if (data.config.has_credentials) {
          setOneRosterHasCredentials(true);
        }
      }
      if (data.status === 'connected') {
        setOneRosterStatus('connected');
      }
    }).catch(function() {});
    // Check district SIS provider
    api.getDistrictConfigStatus().then(function(data) {
      setDistrictSisProvider(data.sis_provider || null);
    }).catch(function() {});
    // Load LTI config on mount
    api.getLTIConfig().then(function(data) {
      setLtiPlatforms(data.platforms || []);
      setLtiToolConfig(data.tool_config || null);
    }).catch(function() {});
    api.getLTIContexts().then(function(data) {
      setLtiContexts(data.contexts || []);
    }).catch(function() {});
    // Check admin status
    api.getAdminStatus().then(function(data) {
      setAdminStatus(data);
    }).catch(function() {});
  }, []);

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
              /* Tools tab removed — Clever handles integration */
              { id: "privacy", label: "Privacy", icon: "Shield" },
              ...(!isCleverUser ? [{ id: "billing", label: "Billing", icon: "CreditCard" }] : []),
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
              <SettingsGeneral
                addToast={addToast}
                adminClaimCode={adminClaimCode}
                adminClaimResult={adminClaimResult}
                adminStatus={adminStatus}
                availableStates={availableStates}
                config={config}
                setAdminClaimCode={setAdminClaimCode}
                setAdminClaimResult={setAdminClaimResult}
                setAdminStatus={setAdminStatus}
                setConfig={setConfig}
                setShowOnboardingWizard={setShowOnboardingWizard}
                setShowVportalPassword={setShowVportalPassword}
                setVportalConfigured={setVportalConfigured}
                setVportalPassword={setVportalPassword}
                setVportalSaving={setVportalSaving}
                showVportalPassword={showVportalPassword}
                vportalConfigured={vportalConfigured}
                vportalPassword={vportalPassword}
                vportalSaving={vportalSaving}
              />
            )}

            {/* Grading Tab */}
            {settingsTab === "grading" && (
              <SettingsGrading
                config={config}
                rubric={rubric}
                setConfig={setConfig}
                setRubric={setRubric}
              />
            )}

            {/* AI Tab */}
            {settingsTab === "ai" && (
              <SettingsAI
                MODEL_COST_PER_ASSIGNMENT={MODEL_COST_PER_ASSIGNMENT}
                addToast={addToast}
                apiKeys={apiKeys}
                config={config}
                globalAINotes={globalAINotes}
                savingApiKeys={savingApiKeys}
                setApiKeys={setApiKeys}
                setConfig={setConfig}
                setGlobalAINotes={setGlobalAINotes}
                setSavingApiKeys={setSavingApiKeys}
                setShowApiKeys={setShowApiKeys}
                showApiKeys={showApiKeys}
              />
            )}

            {/* Tools tab removed */}

            {/* Classroom Tab */}
            {settingsTab === "classroom" && (
              <SettingsClassroom
                accommodationPresets={accommodationPresets}
                activeProvider={activeProvider}
                addToast={addToast}
                addingStudent={addingStudent}
                cleverAccommSuggestions={cleverAccommSuggestions}
                cleverApplying={cleverApplying}
                cleverSelectedSections={cleverSelectedSections}
                cleverSyncResult={cleverSyncResult}
                cleverSyncing={cleverSyncing}
                districtSisProvider={districtSisProvider}
                editStudentData={editStudentData}
                editingStudentId={editingStudentId}
                expandedPeriod={expandedPeriod}
                expandedStudents={expandedStudents}
                focusImportProgress={focusImportProgress}
                focusImporting={focusImporting}
                isCleverUser={isCleverUser}
                loadingExpandedStudents={loadingExpandedStudents}
                ltiContexts={ltiContexts}
                ltiNewPlatform={ltiNewPlatform}
                ltiPlatforms={ltiPlatforms}
                ltiSaving={ltiSaving}
                ltiSelectedContext={ltiSelectedContext}
                ltiShowForm={ltiShowForm}
                ltiSyncLabel={ltiSyncLabel}
                ltiSyncMaxScore={ltiSyncMaxScore}
                ltiSyncResult={ltiSyncResult}
                ltiSyncScores={ltiSyncScores}
                ltiSyncing={ltiSyncing}
                ltiToolConfig={ltiToolConfig}
                newPeriodName={newPeriodName}
                newStudent={newStudent}
                oneRosterAccommodations={oneRosterAccommodations}
                oneRosterApplying={oneRosterApplying}
                oneRosterConfig={oneRosterConfig}
                oneRosterHasCredentials={oneRosterHasCredentials}
                oneRosterSaving={oneRosterSaving}
                oneRosterStatus={oneRosterStatus}
                oneRosterSyncResult={oneRosterSyncResult}
                oneRosterSyncing={oneRosterSyncing}
                oneRosterTestResult={oneRosterTestResult}
                parentContacts={parentContacts}
                parentContactsInputRef={parentContactsInputRef}
                periodInputRef={periodInputRef}
                setAccommEllLanguage={setAccommEllLanguage}
                setAccommodationCustomNotes={setAccommodationCustomNotes}
                setAccommodationModal={setAccommodationModal}
                setAddStudentModal={setAddStudentModal}
                setAddingStudent={setAddingStudent}
                setCleverAccommSuggestions={setCleverAccommSuggestions}
                setCleverApplying={setCleverApplying}
                setCleverSelectedSections={setCleverSelectedSections}
                setCleverSyncResult={setCleverSyncResult}
                setCleverSyncing={setCleverSyncing}
                setEditStudentData={setEditStudentData}
                setEditingStudentId={setEditingStudentId}
                setExpandedPeriod={setExpandedPeriod}
                setExpandedStudents={setExpandedStudents}
                setFocusImportProgress={setFocusImportProgress}
                setFocusImporting={setFocusImporting}
                setLoadingExpandedStudents={setLoadingExpandedStudents}
                setLtiNewPlatform={setLtiNewPlatform}
                setLtiPlatforms={setLtiPlatforms}
                setLtiSaving={setLtiSaving}
                setLtiSelectedContext={setLtiSelectedContext}
                setLtiShowForm={setLtiShowForm}
                setLtiSyncLabel={setLtiSyncLabel}
                setLtiSyncMaxScore={setLtiSyncMaxScore}
                setLtiSyncResult={setLtiSyncResult}
                setLtiSyncScores={setLtiSyncScores}
                setLtiSyncing={setLtiSyncing}
                setLtiToolConfig={setLtiToolConfig}
                setNewPeriodName={setNewPeriodName}
                setNewStudent={setNewStudent}
                setOneRosterAccommodations={setOneRosterAccommodations}
                setOneRosterApplying={setOneRosterApplying}
                setOneRosterConfig={setOneRosterConfig}
                setOneRosterHasCredentials={setOneRosterHasCredentials}
                setOneRosterSaving={setOneRosterSaving}
                setOneRosterStatus={setOneRosterStatus}
                setOneRosterSyncResult={setOneRosterSyncResult}
                setOneRosterSyncing={setOneRosterSyncing}
                setOneRosterTestResult={setOneRosterTestResult}
                setParentContactMapping={setParentContactMapping}
                setPeriods={setPeriods}
                setSelectedAccommodationPresets={setSelectedAccommodationPresets}
                setShowManualSetup={setShowManualSetup}
                setShowOneRosterSecret={setShowOneRosterSecret}
                setStudentAccommodations={setStudentAccommodations}
                setTeacherSisId={setTeacherSisId}
                setUploadingParentContacts={setUploadingParentContacts}
                setUploadingPeriod={setUploadingPeriod}
                showManualSetup={showManualSetup}
                showOneRosterSecret={showOneRosterSecret}
                sortedPeriods={sortedPeriods}
                studentAccommodations={studentAccommodations}
                teacherSisId={teacherSisId}
                uploadingParentContacts={uploadingParentContacts}
                uploadingPeriod={uploadingPeriod}
              />
            )}

            {/* Privacy Tab */}
            {settingsTab === "privacy" && (
              <SettingsPrivacy
                addToast={addToast}
                config={config}
                exportStudentSearch={exportStudentSearch}
                importFileRef={importFileRef}
                importStudentData={importStudentData}
                periods={periods}
                selectedStudentHistory={selectedStudentHistory}
                setConfig={setConfig}
                setExportStudentSearch={setExportStudentSearch}
                setImportStudentData={setImportStudentData}
                setSelectedStudentHistory={setSelectedStudentHistory}
                setStudentHistoryList={setStudentHistoryList}
                setStudentHistoryLoading={setStudentHistoryLoading}
                studentHistoryList={studentHistoryList}
                studentHistoryLoading={studentHistoryLoading}
              />
            )}

            {/* Billing Tab */}
            {settingsTab === "billing" && (
              <SettingsBilling
                addToast={addToast}
                config={config}
                costSummary={costSummary}
                setConfig={setConfig}
                setCostSummary={setCostSummary}
                setSubscription={setSubscription}
                setSubscriptionLoading={setSubscriptionLoading}
                subscription={subscription}
                subscriptionLoading={subscriptionLoading}
              />
            )}

            {/* Resources Tab */}
            {settingsTab === "resources" && (
              <SettingsResources
                addToast={addToast}
                newDocDescription={newDocDescription}
                newDocType={newDocType}
                setNewDocDescription={setNewDocDescription}
                setNewDocType={setNewDocType}
                setSupportDocs={setSupportDocs}
                setUploadingDoc={setUploadingDoc}
                supportDocInputRef={supportDocInputRef}
                supportDocs={supportDocs}
                uploadingDoc={uploadingDoc}
              />
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
});
