# Supabase Authentication Implementation Plan

## Overview

Add Supabase Auth to Graider so teachers must sign up and log in. The landing page handles account creation; the React app handles login + session management. Backend validates JWTs on all teacher API routes using a `before_request` hook (no per-route decorators needed). Email confirmation required before access.

---

## Phase 1: Dependencies & Config

### 1a. Add PyJWT to `requirements.txt`

**File: `requirements.txt`**

Add after the `supabase>=2.0.0` line:

```
# Auth (JWT validation)
PyJWT>=2.8.0
```

### 1b. Add `@supabase/supabase-js` to frontend

```bash
cd frontend && npm install @supabase/supabase-js
```

### 1c. Add `SUPABASE_JWT_SECRET` to `.env`

**File: `.env`**

Add:

```
SUPABASE_JWT_SECRET=<get from Supabase Dashboard > Settings > API > JWT Secret>
```

Also add this to Railway environment variables.

### 1d. Supabase Dashboard Config

In Supabase Dashboard > Authentication > Settings:
- **Enable email confirmations**: ON
- **Site URL**: `https://app.graider.live`
- **Redirect URLs**: Add `https://app.graider.live`

---

## Phase 2: Backend Auth Middleware

### Create `backend/auth.py` (NEW FILE)

```python
"""
Supabase JWT Authentication for Graider.
Validates Bearer tokens on all /api/ routes except public endpoints.
"""
import os
import jwt
from functools import wraps
from flask import request, jsonify, g

# Routes that don't require authentication
PUBLIC_PREFIXES = [
    '/api/student/',       # Student portal (public, students don't have accounts)
]

PUBLIC_EXACT = [
    '/api/status',         # Grading status polling (used before auth check completes)
]


def get_jwt_secret():
    """Get the Supabase JWT secret from environment."""
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        raise RuntimeError('SUPABASE_JWT_SECRET not configured')
    return secret


def validate_token(token):
    """
    Validate a Supabase JWT and return the decoded payload.
    Returns None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=['HS256'],
            audience='authenticated',
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_public_route(path):
    """Check if a route is public (no auth required)."""
    if path in PUBLIC_EXACT:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def init_auth(app):
    """
    Register the before_request auth hook on the Flask app.
    Call this BEFORE registering blueprints.
    """
    @app.before_request
    def check_auth():
        # Skip non-API routes (static files, index.html, etc.)
        if not request.path.startswith('/api/'):
            return None

        # Skip public routes
        if is_public_route(request.path):
            return None

        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header[7:]  # Strip 'Bearer '
        payload = validate_token(token)
        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Attach user info to Flask's g object for use in route handlers
        g.user_id = payload.get('sub')
        g.user_email = payload.get('email', '')
```

### Modify `backend/app.py` — Register auth middleware

**File: `backend/app.py`**

After line 61 (`CORS(app)`), add:

```python
# ══════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════
try:
    from auth import init_auth
    init_auth(app)
except Exception as e:
    print(f"Warning: Auth middleware not loaded: {e}")
```

This goes BEFORE the route registrations at line 1370, so the `before_request` hook fires for all routes.

---

## Phase 3: Frontend Auth — Supabase Client + Login Screen

### 3a. Create `frontend/src/services/supabase.js` (NEW FILE)

```javascript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://hecxqiedfodnpujjriin.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhlY3hxaWVkZm9kbnB1ampyaWluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk4OTA3ODMsImV4cCI6MjA4NTQ2Njc4M30.KUvoxjmnCbZSUZo2a8nIj0UD56KM-CXB0dpZ1iYMwLE'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

> Note: The anon key is a public key (safe to embed). For production, use `VITE_` env vars so Vite injects them at build time.

### 3b. Update `frontend/src/services/api.js` — Inject auth token

**File: `frontend/src/services/api.js`**

Add import at top (after line 4):

```javascript
import { supabase } from './supabase'
```

Add auth header helper (after line 6, before `fetchApi`):

```javascript
/**
 * Get authorization headers with current session token
 */
async function getAuthHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    return { 'Authorization': 'Bearer ' + session.access_token }
  }
  return {}
}
```

Replace the existing `fetchApi` function (lines 11-30) with:

```javascript
async function fetchApi(endpoint, options = {}) {
  try {
    const authHeaders = await getAuthHeaders()
    const response = await fetch(API_BASE + endpoint, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...options.headers,
      },
      ...options,
    })

    if (response.status === 401) {
      // Token expired or invalid — trigger re-login
      window.dispatchEvent(new Event('auth-expired'))
      throw new Error('Session expired. Please log in again.')
    }

    if (!response.ok) {
      throw new Error('API error: ' + response.status)
    }

    return await response.json()
  } catch (error) {
    console.error('API Error (' + endpoint + '):', error)
    throw error
  }
}
```

Also update the 6 functions that use `fetch` directly (bypassing `fetchApi`) to include auth headers. These are: `parseDocument`, `uploadAssessmentTemplate`, `uploadRoster`, `uploadPeriod`, `uploadSupportDocument`, `importAccommodations`.

Example for `parseDocument` (lines 147-157), change to:

```javascript
export async function parseDocument(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/parse-document', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })

  return response.json()
}
```

Apply the same pattern to the other 5 FormData upload functions.

### 3c. Create `frontend/src/components/LoginScreen.jsx` (NEW FILE)

```jsx
import { useState } from 'react'
import { supabase } from '../services/supabase'

export default function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showForgot, setShowForgot] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { data, error: authError } = await supabase.auth.signInWithPassword({
      email: email,
      password: password,
    })

    setLoading(false)

    if (authError) {
      if (authError.message.includes('Email not confirmed')) {
        setError('Please confirm your email before signing in. Check your inbox.')
      } else {
        setError(authError.message)
      }
      return
    }

    onLogin(data.user)
  }

  async function handleForgotPassword(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin,
    })

    setLoading(false)

    if (resetError) {
      setError(resetError.message)
      return
    }

    setForgotSent(true)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      padding: '20px',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        background: 'rgba(255,255,255,0.03)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        border: '1px solid rgba(255,255,255,0.1)',
        padding: '40px',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{
            fontSize: '2rem',
            fontWeight: 800,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            marginBottom: '8px',
          }}>Graider</h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.95rem' }}>
            {showForgot ? 'Reset your password' : 'Sign in to continue'}
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.15)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: '12px',
            padding: '12px 16px',
            marginBottom: '20px',
            color: '#f87171',
            fontSize: '0.9rem',
          }}>{error}</div>
        )}

        {showForgot ? (
          forgotSent ? (
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: '#4ade80', marginBottom: '16px' }}>
                Reset link sent! Check your email.
              </p>
              <button onClick={() => { setShowForgot(false); setForgotSent(false) }}
                className="btn btn-secondary" style={{ width: '100%' }}>
                Back to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleForgotPassword}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '8px' }}>Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@school.edu" required className="input" />
              </div>
              <button type="submit" disabled={loading}
                className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
              <p style={{ textAlign: 'center', marginTop: '16px', fontSize: '0.9rem' }}>
                <a href="#" onClick={(e) => { e.preventDefault(); setShowForgot(false); setError('') }}
                  style={{ color: '#a5b4fc' }}>Back to Sign In</a>
              </p>
            </form>
          )
        ) : (
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '8px' }}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@school.edu" required className="input" />
            </div>
            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '8px' }}>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password" required className="input" />
            </div>
            <button type="submit" disabled={loading}
              className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px', fontSize: '0.9rem' }}>
              <a href="#" onClick={(e) => { e.preventDefault(); setShowForgot(true); setError('') }}
                style={{ color: '#a5b4fc' }}>Forgot password?</a>
              <a href="https://graider.live" style={{ color: 'rgba(255,255,255,0.4)' }}>
                Need an account?
              </a>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
```

### 3d. Modify `frontend/src/App.jsx` — Add auth gate

**File: `frontend/src/App.jsx`**

Add import after line 24 (`import * as api from "./services/api";`):

```javascript
import { supabase } from "./services/supabase";
import LoginScreen from "./components/LoginScreen";
```

Inside the `App()` function, add auth state at the top (before existing `useState` calls):

```javascript
// Auth state
const [user, setUser] = useState(null);
const [authLoading, setAuthLoading] = useState(true);

// Check for existing session on mount
useEffect(() => {
  supabase.auth.getSession().then(({ data: { session } }) => {
    setUser(session?.user ?? null);
    setAuthLoading(false);
  });

  const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
    setUser(session?.user ?? null);
  });

  // Listen for auth-expired events from API layer
  function handleAuthExpired() {
    supabase.auth.signOut();
    setUser(null);
  }
  window.addEventListener('auth-expired', handleAuthExpired);

  return () => {
    subscription.unsubscribe();
    window.removeEventListener('auth-expired', handleAuthExpired);
  };
}, []);
```

Add early returns before the main render (before the first `return` statement in the component):

```javascript
// Auth loading state
if (authLoading) {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
    }}>
      <div className="spin" style={{ width: 40, height: 40, border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#6366f1', borderRadius: '50%' }} />
    </div>
  );
}

// Not logged in — show login screen
if (!user) {
  return <LoginScreen onLogin={setUser} />;
}
```

Add a logout function (near the auth state):

```javascript
async function handleLogout() {
  await supabase.auth.signOut();
  setUser(null);
}
```

Add a logout button in the sidebar (near the theme toggle or bottom of sidebar):

```jsx
<button onClick={handleLogout} title="Sign Out"
  style={{
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    padding: '10px',
    cursor: 'pointer',
    color: 'var(--text-secondary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s ease',
  }}>
  <Icon name="LogOut" size={18} />
</button>
```

---

## Phase 4: Landing Page — Real Supabase Auth

### 4a. Modify `landing/index.html` — Add Supabase CDN + password field

**File: `landing/index.html`**

Add Supabase CDN before `<script src="script.js">` (before line 687):

```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
```

Add password field to signup form. After the email field (after line 633), add:

```html
<div class="form-group">
    <label for="signup-password">Password</label>
    <div class="password-input">
        <input type="password" id="signup-password" placeholder="Create a password (min 6 characters)" required minlength="6">
        <button type="button" class="password-toggle" onclick="togglePassword('signup-password')" aria-label="Toggle password visibility">
            <svg class="eye-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
            </svg>
            <svg class="eye-closed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
            </svg>
        </button>
    </div>
</div>
```

### 4b. Modify `landing/script.js` — Real Supabase auth calls

**File: `landing/script.js`**

Add Supabase client init at the top (after line 12):

```javascript
// Supabase client
const supabaseClient = window.supabase.createClient(
    'https://hecxqiedfodnpujjriin.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhlY3hxaWVkZm9kbnB1ampyaWluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk4OTA3ODMsImV4cCI6MjA4NTQ2Njc4M30.KUvoxjmnCbZSUZo2a8nIj0UD56KM-CXB0dpZ1iYMwLE'
);
```

Replace `handleLogin` function (lines 122-144) with:

```javascript
function handleLogin(event) {
    event.preventDefault();
    var email = document.getElementById('login-email').value;
    var password = document.getElementById('login-password').value;

    if (!email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    var originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing in...';
    submitBtn.disabled = true;

    supabaseClient.auth.signInWithPassword({ email: email, password: password })
        .then(function(result) {
            if (result.error) {
                if (result.error.message.indexOf('Email not confirmed') >= 0) {
                    showFormError('Please confirm your email first. Check your inbox.');
                } else {
                    showFormError(result.error.message);
                }
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
                return;
            }
            // Success - redirect to app
            window.location.href = 'https://app.graider.live';
        })
        .catch(function(err) {
            showFormError('Something went wrong. Please try again.');
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        });
}
```

Replace `handleSignup` function (lines 146-196) with:

```javascript
function handleSignup(event) {
    event.preventDefault();
    var firstName = document.getElementById('signup-first').value;
    var lastName = document.getElementById('signup-last').value;
    var email = document.getElementById('signup-email').value;
    var password = document.getElementById('signup-password').value;
    var terms = document.getElementById('terms').checked;

    if (!firstName || !lastName || !email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    if (password.length < 6) {
        showFormError('Password must be at least 6 characters');
        return;
    }

    if (!terms) {
        showFormError('Please accept the terms and conditions');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Creating account...';
    submitBtn.disabled = true;

    supabaseClient.auth.signUp({
        email: email,
        password: password,
        options: {
            data: {
                first_name: firstName,
                last_name: lastName,
            },
            emailRedirectTo: 'https://app.graider.live',
        }
    })
    .then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
            submitBtn.textContent = 'Create Account';
            submitBtn.disabled = false;
            return;
        }

        // Show confirmation message
        var formContent = event.target.parentElement;
        formContent.innerHTML = '<div style="text-align:center;padding:20px 0;">' +
            '<div style="font-size:3rem;margin-bottom:16px;">&#9993;</div>' +
            '<h2 style="margin-bottom:12px;">Check your email</h2>' +
            '<p style="color:rgba(255,255,255,0.6);margin-bottom:24px;">' +
            'We sent a confirmation link to <strong>' + email + '</strong>. ' +
            'Click the link to activate your account, then sign in at the app.</p>' +
            '<a href="https://app.graider.live" class="btn btn-primary" style="display:inline-flex;">Go to App</a>' +
            '</div>';
    })
    .catch(function(err) {
        showFormError('Something went wrong. Please try again.');
        submitBtn.textContent = 'Create Account';
        submitBtn.disabled = false;
    });
}
```

Replace `handleForgotPassword` function (lines 198-224) with:

```javascript
function handleForgotPassword(event) {
    event.preventDefault();
    var email = document.getElementById('forgot-email').value;

    if (!email) {
        showFormError('Please enter your email');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Sending...';
    submitBtn.disabled = true;

    supabaseClient.auth.resetPasswordForEmail(email, {
        redirectTo: 'https://app.graider.live',
    })
    .then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
            submitBtn.textContent = 'Send Reset Link';
            submitBtn.disabled = false;
            return;
        }

        submitBtn.textContent = 'Link Sent!';
        submitBtn.style.background = '#22c55e';

        setTimeout(function() {
            showLoginForm();
            submitBtn.textContent = 'Send Reset Link';
            submitBtn.style.background = '';
            submitBtn.disabled = false;
        }, 2000);
    })
    .catch(function(err) {
        showFormError('Something went wrong. Please try again.');
        submitBtn.textContent = 'Send Reset Link';
        submitBtn.disabled = false;
    });
}
```

---

## Phase 5: Build & Deploy

After all code changes:

```bash
cd frontend && npm run build    # Rebuilds to backend/static/
```

Add to Railway env vars:
- `SUPABASE_JWT_SECRET` (from Supabase Dashboard > Settings > API > JWT Secret)

Redeploy to Railway.

---

## Phase 6 (Follow-up): Supabase Tables for Per-User Data

> Not in this PR. Planned as separate task after auth works.

Railway's filesystem is ephemeral, so local files (`~/.graider_*`) get wiped on redeploy. After auth is working, migrate these to Supabase tables:

- `teacher_settings` (user_id, rubric_json, global_notes_json)
- `teacher_assignments` (user_id, name, config_json)
- `grading_results` (user_id, student_name, assignment, score, grade, feedback, ...)

Each table scoped by `user_id` from the JWT. This is a separate implementation task.

---

## Files Summary

| Action | File | What |
|--------|------|------|
| CREATE | `backend/auth.py` | JWT validation + `before_request` hook |
| CREATE | `frontend/src/services/supabase.js` | Supabase JS client init |
| CREATE | `frontend/src/components/LoginScreen.jsx` | React login screen |
| MODIFY | `backend/app.py` (line ~62) | Import + call `init_auth(app)` |
| MODIFY | `frontend/src/services/api.js` | Add auth headers to all requests |
| MODIFY | `frontend/src/App.jsx` (top of component) | Auth gate + logout |
| MODIFY | `landing/index.html` | Supabase CDN + password field in signup |
| MODIFY | `landing/script.js` | Replace fake auth with real Supabase calls |
| MODIFY | `requirements.txt` | Add PyJWT |
| MODIFY | `.env` | Add SUPABASE_JWT_SECRET |

---

## Verification

1. **Backend starts**: `cd backend && python app.py` — no import errors
2. **Unauthenticated API blocked**: `curl http://localhost:3000/api/load-rubric` returns 401
3. **Public routes still work**: `curl http://localhost:3000/api/student/join/ABC123` does NOT return 401
4. **Frontend shows login**: Open `http://localhost:5173` — see login screen (not the app)
5. **Signup works**: Go to landing page, create account, receive confirmation email
6. **Login works**: After confirming email, log in at the app — see the full Graider UI
7. **API calls work authenticated**: All tabs (Grade, Results, Builder, etc.) load data normally
8. **Logout works**: Click logout button, returns to login screen
9. **Token expiry handled**: After session expires, user sees login screen (not a broken app)
10. **Build + deploy**: `cd frontend && npm run build` succeeds, Railway deploy works
