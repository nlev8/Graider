import { useState } from 'react'
import { supabase } from '../services/supabase'

export default function LoginScreen({ onLogin, theme, toggleTheme }) {
  const isDark = theme !== 'light';
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showForgot, setShowForgot] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  async function handleOAuth(provider) {
    setError('')
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
        padding: '40px',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <img
            src={isDark ? '/graider-brain-dark.png' : '/graider-brain-light.png'}
            alt="Graider brain"
            style={{ width: 98, height: 98, display: 'block', margin: '0 auto', marginBottom: -86 }}
          />
          <img
            src={isDark ? '/graider-wordmark-dark.png' : '/graider-wordmark-light.png'}
            alt="Graider"
            style={{ width: '85%', maxWidth: 280, display: 'block', margin: '0 auto', marginTop: 24, marginBottom: -40 }}
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

        {showForgot ? (
          forgotSent ? (
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: '#4ade80', marginBottom: '16px' }}>
                Reset link sent! Check your email.
              </p>
              <button onClick={() => { setShowForgot(false); setForgotSent(false) }}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '12px',
                  border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'),
                  background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                  color: isDark ? 'white' : '#1e293b',
                  cursor: 'pointer',
                  fontSize: '0.95rem',
                  fontFamily: 'inherit',
                }}>
                Back to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleForgotPassword}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', marginBottom: '8px' }}>Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@school.edu" required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
                    background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
                    color: isDark ? 'white' : '#1e293b',
                    fontSize: '0.95rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }} />
              </div>
              <button type="submit" disabled={loading}
                style={{
                  width: '100%',
                  padding: '14px',
                  borderRadius: '12px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: 'white',
                  cursor: loading ? 'wait' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 600,
                  fontFamily: 'inherit',
                  opacity: loading ? 0.7 : 1,
                }}>
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
              <p style={{ textAlign: 'center', marginTop: '16px', fontSize: '0.9rem' }}>
                <a href="#" onClick={(e) => { e.preventDefault(); setShowForgot(false); setError('') }}
                  style={{ color: isDark ? '#a5b4fc' : '#4f46e5', textDecoration: 'none' }}>Back to Sign In</a>
              </p>
            </form>
          )
        ) : (
          <>
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', marginBottom: '8px' }}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@school.edu" required
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
                  background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
                  color: isDark ? 'white' : '#1e293b',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }} />
            </div>
            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', marginBottom: '8px' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password" required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    paddingRight: '44px',
                    borderRadius: '12px',
                    border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
                    background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
                    color: isDark ? 'white' : '#1e293b',
                    fontSize: '0.95rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }} />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', padding: 0,
                    color: isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.35)', fontSize: '1.1rem', lineHeight: 1,
                  }}
                  aria-label="Toggle password visibility"
                >{showPassword ? String.fromCodePoint(0x1F441) : String.fromCodePoint(0x1F441, 0x200D, 0x1F5E8)}</button>
              </div>
            </div>
            <button type="submit" disabled={loading}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: '12px',
                border: 'none',
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                color: 'white',
                cursor: loading ? 'wait' : 'pointer',
                fontSize: '1rem',
                fontWeight: 600,
                fontFamily: 'inherit',
                opacity: loading ? 0.7 : 1,
              }}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px', fontSize: '0.9rem' }}>
              <a href="#" onClick={(e) => { e.preventDefault(); setShowForgot(true); setError('') }}
                style={{ color: isDark ? '#a5b4fc' : '#4f46e5', textDecoration: 'none' }}>Forgot password?</a>
              <a href="https://graider.live" style={{ color: isDark ? 'rgba(255,255,255,0.4)' : '#94a3b8', textDecoration: 'none' }}>
                Need an account?
              </a>
            </div>
          </form>

          {/* OAuth divider */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            margin: '24px 0 20px',
          }}>
            <div style={{ flex: 1, height: 1, background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} />
            <span style={{ fontSize: '0.8rem', color: isDark ? 'rgba(255,255,255,0.4)' : '#94a3b8' }}>or continue with</span>
            <div style={{ flex: 1, height: 1, background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} />
          </div>

          {/* Social auth buttons */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => handleOAuth('google')}
              style={{
                flex: 1, padding: '12px', borderRadius: '12px',
                border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                color: isDark ? 'white' : '#1e293b', fontSize: '0.9rem', fontWeight: 500, fontFamily: 'inherit',
              }}>
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Google
            </button>
            <button onClick={() => handleOAuth('azure')}
              style={{
                flex: 1, padding: '12px', borderRadius: '12px',
                border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                color: isDark ? 'white' : '#1e293b', fontSize: '0.9rem', fontWeight: 500, fontFamily: 'inherit',
              }}>
              <svg width="18" height="18" viewBox="0 0 24 24">
                <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
                <rect x="13" y="1" width="10" height="10" fill="#7FBA00"/>
                <rect x="1" y="13" width="10" height="10" fill="#00A4EF"/>
                <rect x="13" y="13" width="10" height="10" fill="#FFB900"/>
              </svg>
              Microsoft
            </button>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
