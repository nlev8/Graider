export default function ForgotPasswordView(props) {
  const { showForgot, forgotSent, setForgotSent, setShowForgot, email, setEmail, loading, setError, handleForgotPassword, isDark } = props;
  if (!(showForgot)) return null;
  return (
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
              padding: '10px 14px',
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
  );
}
