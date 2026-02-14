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
            style={{ width: 64, height: 64, marginBottom: 12, display: 'block', margin: '0 auto 12px' }}
          />
          <img
            src={isDark ? '/graider-wordmark-dark.png' : '/graider-wordmark-light.png'}
            alt="Graider"
            style={{ height: 36, marginBottom: 8, display: 'block', margin: '0 auto 8px' }}
          />
          <p style={{ color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', fontSize: '0.95rem' }}>
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
        )}
      </div>
    </div>
  )
}
