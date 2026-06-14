import React from "react";
import Icon from "../../components/Icon";
import SettingsGeneral from "../../components/SettingsGeneral";
import SettingsGrading from "../../components/SettingsGrading";
import SettingsBilling from "../../components/SettingsBilling";
import SettingsAI from "../../components/SettingsAI";
import SettingsPrivacy from "../../components/SettingsPrivacy";
import SettingsResources from "../../components/SettingsResources";
import SettingsSubTabNav from "./SettingsSubTabNav";
import ClassroomSection from "./ClassroomSection";

/*
 * SettingsTabPanel — the settings glass-card panel, extracted from SettingsTab
 * (CQ wave-10 split). Owns no state or effects; every value and handler it
 * uses arrives as a prop from SettingsTab. Pure-prop pass-through shell:
 * moving JSX, not adding logic.
 *
 * Prop-threading strategy: SettingsTab passes every prop the sub-tabs need
 * (integration + modals spreads + local state). SettingsTabPanel uses
 * named destructuring for the props it reads directly in JSX (settingsTab,
 * isCleverUser, settingsTab for each conditional), then spreads the full
 * props object into ClassroomSection (which expects all the same keys) and
 * passes individual named props into each tab component exactly as SettingsTab
 * originally did — no prop renamed, no logic added or removed.
 */
export default function SettingsTabPanel(props) {
  const {
    settingsTab, setSettingsTab, isCleverUser, addToast,
    // General tab
    adminClaimCode, adminClaimResult, adminStatus, availableStates,
    config, setConfig,
    setAdminClaimCode, setAdminClaimResult, setAdminStatus,
    setShowOnboardingWizard, setShowVportalPassword,
    setVportalConfigured, setVportalPassword, setVportalSaving,
    showVportalPassword, vportalConfigured, vportalPassword, vportalSaving,
    // Grading tab
    rubric, setRubric,
    // AI tab
    MODEL_COST_PER_ASSIGNMENT, apiKeys, globalAINotes,
    savingApiKeys, setApiKeys, setGlobalAINotes,
    setSavingApiKeys, setShowApiKeys, showApiKeys,
    // Billing tab
    costSummary, setCostSummary,
    setSubscription, setSubscriptionLoading, subscription, subscriptionLoading,
    // Privacy tab
    exportStudentSearch, importFileRef, importStudentData, periods,
    selectedStudentHistory, setExportStudentSearch, setImportStudentData,
    setSelectedStudentHistory, setStudentHistoryList, setStudentHistoryLoading,
    studentHistoryList, studentHistoryLoading,
    // Resources tab
    newDocDescription, newDocType, setNewDocDescription, setNewDocType,
    setSupportDocs, setUploadingDoc, supportDocInputRef, supportDocs, uploadingDoc,
  } = props;

  return (
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

      {/* Settings Sub-tabs — ./SettingsSubTabNav */}
      <SettingsSubTabNav
        settingsTab={settingsTab}
        setSettingsTab={setSettingsTab}
        isCleverUser={isCleverUser}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
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

        {/* Classroom Tab — guards on settingsTab === "classroom" internally.
            Receives the full props object (integration cluster + modal openers
            + flat classroom props) — identical to what SettingsTab threaded
            into ClassroomSection before the wave-10 split; no key added or
            dropped. */}
        <ClassroomSection {...props} />

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
  );
}
