import React from "react";
import SettingsClassroom from "../../components/SettingsClassroom";

/*
 * ClassroomSection — the `classroom` sub-tab glue, relocated from
 * SettingsTab.jsx (CQ wave-9 split). The `{settingsTab === "classroom" && ...}`
 * guard became the early return below (identical mount/unmount semantics);
 * the <SettingsClassroom /> call itself is verbatim. Props arrive as
 * {...integration} + {...modals} spreads plus the flat shell props, and are
 * destructured back to the original names so the JSX is unchanged.
 */
export default function ClassroomSection(props) {
  const {
    settingsTab,
    // useIntegrationState cluster
    activeProvider, cleverAccommSuggestions, cleverApplying,
    cleverSelectedSections, cleverSyncResult, cleverSyncing,
    districtSisProvider, isCleverUser, ltiContexts, ltiNewPlatform,
    ltiPlatforms, ltiSaving, ltiSelectedContext, ltiShowForm, ltiSyncLabel,
    ltiSyncMaxScore, ltiSyncResult, ltiSyncScores, ltiSyncing, ltiToolConfig,
    oneRosterAccommodations, oneRosterApplying, oneRosterConfig,
    oneRosterHasCredentials, oneRosterSaving, oneRosterStatus,
    oneRosterSyncResult, oneRosterSyncing, oneRosterTestResult,
    setCleverAccommSuggestions, setCleverApplying, setCleverSelectedSections,
    setCleverSyncResult, setCleverSyncing, setLtiNewPlatform, setLtiPlatforms,
    setLtiSaving, setLtiSelectedContext, setLtiShowForm, setLtiSyncLabel,
    setLtiSyncMaxScore, setLtiSyncResult, setLtiSyncScores, setLtiSyncing,
    setLtiToolConfig, setOneRosterAccommodations, setOneRosterApplying,
    setOneRosterConfig, setOneRosterHasCredentials, setOneRosterSaving,
    setOneRosterStatus, setOneRosterSyncResult, setOneRosterSyncing,
    setOneRosterTestResult, setShowManualSetup, setShowOneRosterSecret,
    setTeacherSisId, showManualSetup, showOneRosterSecret, teacherSisId,
    // useSettingsModalsState cluster (modal openers + accommodation form setters)
    setAccommEllLanguage, setAccommodationCustomNotes, setAccommodationModal,
    setAddStudentModal, setParentContactMapping,
    setSelectedAccommodationPresets,
    // flat shell props
    accommodationPresets, addToast, addingStudent, editStudentData,
    editingStudentId, expandedPeriod, expandedStudents, focusImportProgress,
    focusImporting, loadingExpandedStudents, newPeriodName, newStudent,
    parentContacts, parentContactsInputRef, periodInputRef, setAddingStudent,
    setEditStudentData, setEditingStudentId, setExpandedPeriod,
    setExpandedStudents, setFocusImportProgress, setFocusImporting,
    setLoadingExpandedStudents, setNewPeriodName, setNewStudent, setPeriods,
    setStudentAccommodations, setUploadingParentContacts, setUploadingPeriod,
    sortedPeriods, studentAccommodations, uploadingParentContacts,
    uploadingPeriod,
  } = props;

  if (settingsTab !== "classroom") return null;

  return (
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
  );
}
