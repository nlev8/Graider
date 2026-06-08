import { useState, useEffect, useRef } from "react";
import { supabase } from "../services/supabase";
import { initPostHog, identifyUser, resetUser } from "../services/posthog";

/*
 * useAuthSession — the auth lifecycle pushed down from the App.jsx shell (App.jsx
 * decomposition, slice 3). Owns the sticky `user` state + the Supabase
 * onAuthStateChange listener (SIGNED_OUT / PASSWORD_RECOVERY), the Clever/ClassLink
 * session-redirect bootstrap, the approval-gate check, the PostHog identify effect,
 * and handleLogout. The entire contiguous auth block (App.jsx:251-490) moved VERBATIM
 * as a unit — so React hook-call order is preserved exactly — with two mechanical
 * adjustments required by the new file location:
 *   1. `isLocalhost` is now a parameter (it was a const used in ~10 places across App,
 *      so it stays computed in App and is passed in here).
 *   2. the dynamic `import('./services/api')` becomes `import('../services/api')`.
 * Pre-existing dead code (the unused `setUser` wrapper and the unused `aiNoticeDismissed`
 * state) is moved verbatim too — removing it would be a cleanup, out of scope for a
 * behavior-preserving move; a follow-up can delete it.
 */
export function useAuthSession(isLocalhost) {
  // Auth state — user is "sticky": once logged in, can ONLY be cleared
  // by explicit handleLogout(). This prevents all spurious sign-out events
  // from kicking the user out (Supabase internal auto-refresh failures,
  // race conditions, etc.).
  const [user, _setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [userApproved, setUserApproved] = useState(null); // null=loading, true/false
  const [aiNoticeDismissed, setAiNoticeDismissed] = useState(function() {
    return localStorage.getItem('graider_ai_notice_dismissed') === 'true';
  });
  const logoutIntentRef = useRef(false);

  function setUser(u) {
    if (u == null && !logoutIntentRef.current) {
      // Block all automatic setUser(null) — only explicit logout can clear
      console.warn('Blocked automatic setUser(null)');
      return;
    }
    logoutIntentRef.current = false;
    _setUser(u);
    window.__graiderUser = u;  // lets api.js detect Clever users
  }

  // Check URL hash for recovery token BEFORE Supabase consumes it
  const [showPasswordReset, setShowPasswordReset] = useState(() => {
    const hash = window.location.hash;
    return hash.includes('type=recovery');
  });

  // Initialize PostHog (skip on localhost)
  useEffect(() => {
    if (!isLocalhost) initPostHog();
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    // Check for Clever login redirect (before localhost check — works everywhere)
    const urlParams = new URLSearchParams(window.location.search);
    const cleverLogin = urlParams.get('clever_login');
    const cleverError = urlParams.get('clever_error');

    if (cleverLogin === 'success') {
      fetch('/api/clever/session')
        .then(function(r) { return r.json() })
        .then(function(data) {
          if (data.authenticated) {
            _setUser({
              id: 'clever:' + data.clever_id,
              email: data.email,
              user_metadata: {
                name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''),
                approved: true,
              },
            });
            window.__graiderUser = { id: 'clever:' + data.clever_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'clever' };
            setAuthLoading(false);
          }
        })
        .catch(function(err) { console.error('Clever session check failed:', err) });
      window.history.replaceState({}, '', '/');
      return;
    }
    if (cleverError) {
      console.error('Clever login error:', cleverError);
      var cleverErrorMessages = {
        'missing_code': 'Login was cancelled or interrupted. Please try again.',
        'state_mismatch': 'Login session expired. Please try again.',
        'token_exchange_failed': 'Could not complete login with Clever. Please try again.',
        'user_fetch_failed': 'Could not retrieve your account information from Clever.',
        'students_use_portal': 'Student accounts should use the student portal, not the teacher login.',
        'student_not_enrolled': 'Your account was not found. Ask your teacher to sync the class roster.',
        'unsupported_role': 'This account type is not supported.',
        'role_not_permitted': 'This Clever account type cannot access the teacher dashboard.',
      };
      var friendlyMsg = cleverErrorMessages[cleverError] || ('Clever login failed: ' + cleverError);
      // Store error so LoginScreen can display it
      window.__cleverLoginError = friendlyMsg;
      window.history.replaceState({}, '', '/');
    }

    // Check for ClassLink login redirect
    var classlinkLogin = urlParams.get('classlink_login');
    var classlinkError = urlParams.get('classlink_error');

    if (classlinkLogin === 'success') {
      fetch('/api/classlink/session')
        .then(function(r) { return r.json() })
        .then(function(data) {
          if (data.authenticated) {
            _setUser({
              id: data.user_id,
              email: data.email,
              user_metadata: {
                name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''),
                approved: true,
              },
            });
            window.__graiderUser = { id: data.user_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'classlink' };
            setAuthLoading(false);
          }
        })
        .catch(function(err) { console.error('ClassLink session check failed:', err) });
      window.history.replaceState({}, '', '/');
      return;
    }
    if (classlinkError) {
      console.error('ClassLink login error:', classlinkError);
      var classlinkErrorMessages = {
        'no_code': 'Login was cancelled or interrupted. Please try again.',
        'state_mismatch': 'Login session expired. Please try again.',
        'token_failed': 'Could not complete login with ClassLink. Please try again.',
        'no_token': 'Could not complete login with ClassLink. Please try again.',
        'token_error': 'Could not complete login with ClassLink. Please try again.',
        'userinfo_failed': 'Could not retrieve your account information from ClassLink.',
        'userinfo_error': 'Could not retrieve your account information from ClassLink.',
        'account_conflict': 'We could not match your ClassLink account to a Graider account. Please contact your administrator.',
      };
      var classlinkFriendlyMsg = classlinkErrorMessages[classlinkError] || ('ClassLink login failed: ' + classlinkError);
      window.__cleverLoginError = classlinkFriendlyMsg;
      window.history.replaceState({}, '', '/');
    }

    if (isLocalhost) {
      _setUser({ id: 'local-dev', email: 'dev@localhost' });
      setAuthLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data: { session } }) => {
      _setUser(session?.user ?? null);
      setAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT') {
        // Only clear user if explicit logout was requested
        if (logoutIntentRef.current) {
          _setUser(null);
          approvalConfirmedRef.current = false;
          logoutIntentRef.current = false;
        }
      } else if (session?.user) {
        _setUser(session.user);
      }
      if (event === 'PASSWORD_RECOVERY') {
        setShowPasswordReset(true);
      }
    });

    // auth-expired is only honored for explicit logout flow
    function handleAuthExpired() {
      console.warn('auth-expired event received, ignoring (use Sign Out button)');
    }
    window.addEventListener('auth-expired', handleAuthExpired);

    return () => {
      subscription.unsubscribe();
      window.removeEventListener('auth-expired', handleAuthExpired);
    };
  }, []);

  // Approval gate check
  const approvalConfirmedRef = useRef(false);
  useEffect(() => {
    if (!user || isLocalhost) {
      setUserApproved(true);
      approvalConfirmedRef.current = true;
      return;
    }

    // Once confirmed, don't re-check on token refreshes
    if (approvalConfirmedRef.current) {
      setUserApproved(true);
      return;
    }

    // Check local JWT metadata first (instant, no API call).
    // VB10: approval is authoritative only in app_metadata (service-role-only).
    // user_metadata.approved is client-settable at signUp and must NOT be
    // trusted — the backend gate ignores it, so trusting it here only produces
    // a misleading UI shell + noisy 403s.
    if (user.app_metadata && user.app_metadata.approved) {
      setUserApproved(true);
      approvalConfirmedRef.current = true;
      return;
    }

    // JWT metadata may be stale — call backend for fresh check via admin API
    async function checkApproval() {
      try {
        const { getAuthHeaders } = await import('../services/api');
        const headers = await getAuthHeaders();
        const res = await fetch('/api/auth/approval-status', {
          headers: { ...headers },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.approved === true) {
            approvalConfirmedRef.current = true;
            setUserApproved(true);
          } else {
            setUserApproved(false);
          }
        } else if (res.status === 403) {
          // Explicitly denied — user is not approved
          setUserApproved(false);
        }
        // On 500/network errors, leave userApproved as null (loading)
        // so the user sees a spinner instead of being kicked out
      } catch {
        // Network error — don't kick user out, keep showing loading
        console.warn('Approval check failed (network error), will retry');
      }
    }
    checkApproval();

    function handleNotApproved() {
      // Only kick out if we never confirmed approval in this session
      if (!approvalConfirmedRef.current) {
        checkApproval();
      }
    }
    window.addEventListener('account-not-approved', handleNotApproved);
    return () => window.removeEventListener('account-not-approved', handleNotApproved);
  }, [user, isLocalhost]);

  // Identify user in PostHog when they log in
  useEffect(() => {
    if (user && !isLocalhost) identifyUser(user);
  }, [user]);

  async function handleLogout() {
    // Clear SSO sessions for all providers (idempotent — no-op when not authenticated)
    await Promise.allSettled([
      fetch('/api/clever/logout', { method: 'POST', credentials: 'include' }),
      fetch('/api/classlink/logout', { method: 'POST', credentials: 'include' }),
    ]);
    logoutIntentRef.current = true;
    approvalConfirmedRef.current = false;
    resetUser();
    await supabase.auth.signOut();
    _setUser(null);
    window.__graiderUser = null;
  }

  return {
    user,
    _setUser,
    authLoading,
    userApproved,
    showPasswordReset,
    setShowPasswordReset,
    handleLogout,
  };
}
