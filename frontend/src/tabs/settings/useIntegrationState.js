import { useEffect, useState } from "react";
import * as api from "../../services/api";

/*
 * useIntegrationState — owns the SIS/LMS integration state cluster (Clever,
 * OneRoster, LTI 1.3, district SIS provider, admin access, available states)
 * plus the single mount-init effect, relocated verbatim from SettingsTab.jsx
 * (CQ wave-9 split). Provider detection (isCleverUser / activeProvider) is
 * recomputed each render exactly as it was in the SettingsTab body. The hook
 * is called unconditionally from the SettingsTab shell; the effect's `[]`
 * dep array is byte-identical to the original.
 */
export default function useIntegrationState() {
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

  return {
    activeProvider,
    adminClaimCode, setAdminClaimCode,
    adminClaimResult, setAdminClaimResult,
    adminStatus, setAdminStatus,
    availableStates, setAvailableStates,
    cleverAccommSuggestions, setCleverAccommSuggestions,
    cleverApplying, setCleverApplying,
    cleverSelectedSections, setCleverSelectedSections,
    cleverSyncResult, setCleverSyncResult,
    cleverSyncing, setCleverSyncing,
    districtSisProvider, setDistrictSisProvider,
    isCleverUser,
    ltiContexts, setLtiContexts,
    ltiNewPlatform, setLtiNewPlatform,
    ltiPlatforms, setLtiPlatforms,
    ltiSaving, setLtiSaving,
    ltiSelectedContext, setLtiSelectedContext,
    ltiShowForm, setLtiShowForm,
    ltiSyncLabel, setLtiSyncLabel,
    ltiSyncMaxScore, setLtiSyncMaxScore,
    ltiSyncResult, setLtiSyncResult,
    ltiSyncScores, setLtiSyncScores,
    ltiSyncing, setLtiSyncing,
    ltiToolConfig, setLtiToolConfig,
    oneRosterAccommodations, setOneRosterAccommodations,
    oneRosterApplying, setOneRosterApplying,
    oneRosterConfig, setOneRosterConfig,
    oneRosterHasCredentials, setOneRosterHasCredentials,
    oneRosterSaving, setOneRosterSaving,
    oneRosterStatus, setOneRosterStatus,
    oneRosterSyncResult, setOneRosterSyncResult,
    oneRosterSyncing, setOneRosterSyncing,
    oneRosterTestResult, setOneRosterTestResult,
    showManualSetup, setShowManualSetup,
    showOneRosterSecret, setShowOneRosterSecret,
    teacherSisId, setTeacherSisId,
  };
}
