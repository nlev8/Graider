import React, { useRef, useState } from "react";
import SettingsModals from "./settings/SettingsModals";
import SettingsTabPanel from "./settings/SettingsTabPanel";
import useIntegrationState from "./settings/useIntegrationState";
import useSettingsModalsState from "./settings/useSettingsModalsState";

/*
 * SettingsTab — the Settings dashboard tab. Thin hub shell after the CQ
 * wave-10 split: it owns the cross-section settings UI state below (pushed
 * down from the App.jsx shell in the App.jsx-decomposition slice 3), pulls
 * the integration cluster from ./settings/useIntegrationState and the
 * shell-modal cluster from ./settings/useSettingsModalsState, and composes
 * the presentational children (SettingsTabPanel for the glass-card panel
 * and all tab content; SettingsModals for the four shell-level modals).
 * Remaining props are cross-tab/shared state still owned by App (e.g.
 * config, rubric, periods, roster/SIS).
 */
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
  subscription,
  setSubscription,
  subscriptionLoading,
  setSubscriptionLoading,
  periods,
  setPeriods,
  rosters,
  setRosters,
  studentAccommodations,
  setStudentAccommodations,
  vportalEmail,
  setVportalEmail,
  vportalConfigured,
  setVportalConfigured,
  supportDocs,
  setSupportDocs,
  assessmentTemplates,
  setAssessmentTemplates,
  uploadingTemplate,
  setUploadingTemplate,
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
  const [addingStudent, setAddingStudent] = useState(false);
  const [costSummary, setCostSummary] = useState(null);
  const [editStudentData, setEditStudentData] = useState({});
  const [editingStudentId, setEditingStudentId] = useState(null);
  const [expandedPeriod, setExpandedPeriod] = useState(null);
  const [expandedStudents, setExpandedStudents] = useState([]);
  const [exportStudentSearch, setExportStudentSearch] = useState({ active: false, query: "", results: [], allStudents: [] });
  const [focusImportProgress, setFocusImportProgress] = useState("");
  const [focusImporting, setFocusImporting] = useState(false);
  const [importStudentData, setImportStudentData] = useState({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" });
  const [loadingExpandedStudents, setLoadingExpandedStudents] = useState(false);
  const [newDocDescription, setNewDocDescription] = useState("");
  const [newDocType, setNewDocType] = useState("curriculum");
  const [newPeriodName, setNewPeriodName] = useState("");
  const [newStudent, setNewStudent] = useState({ name: '', student_id: '', grade: '', parent_emails: '', parent_phones: '' });
  const [parentContacts, setParentContacts] = useState(null);
  const [savingApiKeys, setSavingApiKeys] = useState(false);
  const [selectedStudentHistory, setSelectedStudentHistory] = useState(null);
  const [showApiKeys, setShowApiKeys] = useState({ openai: false, anthropic: false, gemini: false });
  const [studentHistoryList, setStudentHistoryList] = useState([]);
  const [studentHistoryLoading, setStudentHistoryLoading] = useState(false);
  const [syncingCloud, setSyncingCloud] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadingParentContacts, setUploadingParentContacts] = useState(false);
  const [uploadingPeriod, setUploadingPeriod] = useState(false);
  const [vportalPassword, setVportalPassword] = useState("");
  const [vportalSaving, setVportalSaving] = useState(false);
  const [showVportalPassword, setShowVportalPassword] = useState(false);
  const periodInputRef = useRef(null);
  const parentContactsInputRef = useRef(null);
  const supportDocInputRef = useRef(null);
  const importFileRef = useRef(null);

  // Integration cluster (Clever / OneRoster / LTI / district SIS / admin) +
  // the single mount-init effect — ./settings/useIntegrationState (CQ wave-9).
  const integration = useIntegrationState();
  // Shell-level modal state cluster — ./settings/useSettingsModalsState.
  const modals = useSettingsModalsState();

  return (
    <>
      {/* Settings glass-card panel — ./settings/SettingsTabPanel */}
      <SettingsTabPanel
        {...integration}
        {...modals}
        settingsTab={settingsTab}
        setSettingsTab={setSettingsTab}
        addToast={addToast}
        config={config}
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
        rubric={rubric}
        setRubric={setRubric}
        MODEL_COST_PER_ASSIGNMENT={MODEL_COST_PER_ASSIGNMENT}
        apiKeys={apiKeys}
        globalAINotes={globalAINotes}
        savingApiKeys={savingApiKeys}
        setApiKeys={setApiKeys}
        setGlobalAINotes={setGlobalAINotes}
        setSavingApiKeys={setSavingApiKeys}
        setShowApiKeys={setShowApiKeys}
        showApiKeys={showApiKeys}
        costSummary={costSummary}
        setCostSummary={setCostSummary}
        setSubscription={setSubscription}
        setSubscriptionLoading={setSubscriptionLoading}
        subscription={subscription}
        subscriptionLoading={subscriptionLoading}
        exportStudentSearch={exportStudentSearch}
        importFileRef={importFileRef}
        importStudentData={importStudentData}
        periods={periods}
        selectedStudentHistory={selectedStudentHistory}
        setExportStudentSearch={setExportStudentSearch}
        setImportStudentData={setImportStudentData}
        setSelectedStudentHistory={setSelectedStudentHistory}
        setStudentHistoryList={setStudentHistoryList}
        setStudentHistoryLoading={setStudentHistoryLoading}
        studentHistoryList={studentHistoryList}
        studentHistoryLoading={studentHistoryLoading}
        newDocDescription={newDocDescription}
        newDocType={newDocType}
        setNewDocDescription={setNewDocDescription}
        setNewDocType={setNewDocType}
        setSupportDocs={setSupportDocs}
        setUploadingDoc={setUploadingDoc}
        supportDocInputRef={supportDocInputRef}
        supportDocs={supportDocs}
        uploadingDoc={uploadingDoc}
        accommodationPresets={accommodationPresets}
        addingStudent={addingStudent}
        editStudentData={editStudentData}
        editingStudentId={editingStudentId}
        expandedPeriod={expandedPeriod}
        expandedStudents={expandedStudents}
        focusImportProgress={focusImportProgress}
        focusImporting={focusImporting}
        loadingExpandedStudents={loadingExpandedStudents}
        newPeriodName={newPeriodName}
        newStudent={newStudent}
        parentContacts={parentContacts}
        parentContactsInputRef={parentContactsInputRef}
        periodInputRef={periodInputRef}
        setAddingStudent={setAddingStudent}
        setEditStudentData={setEditStudentData}
        setEditingStudentId={setEditingStudentId}
        setExpandedPeriod={setExpandedPeriod}
        setExpandedStudents={setExpandedStudents}
        setFocusImportProgress={setFocusImportProgress}
        setFocusImporting={setFocusImporting}
        setLoadingExpandedStudents={setLoadingExpandedStudents}
        setNewPeriodName={setNewPeriodName}
        setNewStudent={setNewStudent}
        setPeriods={setPeriods}
        setStudentAccommodations={setStudentAccommodations}
        setUploadingParentContacts={setUploadingParentContacts}
        setUploadingPeriod={setUploadingPeriod}
        sortedPeriods={sortedPeriods}
        studentAccommodations={studentAccommodations}
        uploadingParentContacts={uploadingParentContacts}
        uploadingPeriod={uploadingPeriod}
      />

      {/* Shell-level modals (roster mapping / parent contacts / add student /
          accommodations) — ./settings/SettingsModals; each guards its own
          `show` flag internally */}
      <SettingsModals
        {...modals}
        accommodationPresets={accommodationPresets}
        addToast={addToast}
        setParentContacts={setParentContacts}
        setRosters={setRosters}
        setStudentAccommodations={setStudentAccommodations}
        setUploadingParentContacts={setUploadingParentContacts}
        sortedPeriods={sortedPeriods}
        uploadingParentContacts={uploadingParentContacts}
      />
    </>
  );
});
