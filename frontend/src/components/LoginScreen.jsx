import { useState } from 'react'
import { supabase } from '../services/supabase'
import { track } from '../services/posthog'
import ForgotPasswordView from './login-screen/ForgotPasswordView'
import SignInView from './login-screen/SignInView'

export default function LoginScreen({ onLogin, theme, toggleTheme }) {
  const isDark = theme !== 'light';
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(window.__cleverLoginError || '')
  const [showForgot, setShowForgot] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  async function handleOAuth(provider) {
    setError('')
    track('auth_attempted', { method: provider })
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: window.location.origin,
        ...(provider === 'azure' ? { scopes: 'email profile openid' } : {}),
      },
    })
    if (oauthError) setError(oauthError.message)
  }

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
      track('auth_attempted', { method: 'email', success: false })
      if (authError.message.includes('Email not confirmed')) {
        setError('Please confirm your email before signing in. Check your inbox.')
      } else {
        setError(authError.message)
      }
      return
    }

    track('auth_attempted', { method: 'email', success: true })
    onLogin(data.user)
  }

  async function handleForgotPassword(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: 'https://app.graider.live',
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
      overflowY: 'auto',
      background: isDark
        ? 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)'
        : 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%)',
      padding: '20px',
      position: 'relative',
    }}>
      {/* Theme toggle */}
      {toggleTheme && (
        <button
          onClick={toggleTheme}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            position: 'absolute', top: 20, right: 20,
            width: 40, height: 40, borderRadius: 12,
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
            border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.5)',
            fontSize: '1.2rem', padding: 0, fontFamily: 'inherit',
          }}
        >
          {isDark ? '\u2600\uFE0F' : '\uD83C\uDF19'}
        </button>
      )}
      <div style={{
        width: '100%',
        maxWidth: '400px',
        background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.8)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
        padding: '28px 32px',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
          <img
            src={isDark ? '/graider-brain-dark.png' : '/graider-brain-light.png'}
            alt="Graider brain"
            style={{ width: 95, height: 95, display: 'block', margin: '0 auto', marginBottom: -72 }}
          />
          <img
            src={isDark ? '/graider-wordmark-dark.png' : '/graider-wordmark-light.png'}
            alt="Graider"
            style={{ width: '75%', maxWidth: 240, display: 'block', margin: '0 auto', marginTop: 14, marginBottom: -32 }}
          />
          <p style={{ color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', fontSize: '0.95rem', margin: '0' }}>
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

        <ForgotPasswordView
          showForgot={showForgot}
          forgotSent={forgotSent}
          setForgotSent={setForgotSent}
          setShowForgot={setShowForgot}
          email={email}
          setEmail={setEmail}
          loading={loading}
          setError={setError}
          handleForgotPassword={handleForgotPassword}
          isDark={isDark}
        />
        <SignInView
          showForgot={showForgot}
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          showPassword={showPassword}
          setShowPassword={setShowPassword}
          loading={loading}
          setError={setError}
          setShowForgot={setShowForgot}
          handleLogin={handleLogin}
          handleOAuth={handleOAuth}
          isDark={isDark}
        />
        <div style={{ textAlign: "center", marginTop: "12px", borderTop: "1px solid " + (isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"), paddingTop: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
          <a href="/student" style={{ color: "#94a3b8", fontSize: "0.85rem", textDecoration: "none" }}>
            I'm a student — go to Student Portal
          </a>
          <a href="/district" style={{ color: "#64748b", fontSize: "0.75rem", textDecoration: "none" }}>
            District Administration
          </a>
        </div>
      </div>
    </div>
  )
}
