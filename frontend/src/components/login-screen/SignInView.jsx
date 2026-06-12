export default function SignInView(props) {
  const { showForgot, email, setEmail, password, setPassword, showPassword, setShowPassword, loading, setError, setShowForgot, handleLogin, handleOAuth, isDark } = props;
  if (showForgot) return null;
  return (
          <>
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', marginBottom: '4px' }}>Email</label>
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
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: isDark ? 'rgba(255,255,255,0.6)' : '#475569', marginBottom: '4px' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password" required
                  style={{
                    width: '100%',
                    padding: '10px 14px',
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
            margin: '16px 0 12px',
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

          {/* ClassLink SSO */}
          <button onClick={async () => {
            setError('');
            try {
              var resp = await fetch('/api/classlink/login-url');
              var data = await resp.json();
              if (data.url) {
                window.location.href = data.url;
              } else {
                setError('ClassLink login not configured');
              }
            } catch (err) {
              setError('Could not connect to ClassLink');
            }
          }}
            style={{
              width: '100%',
              marginTop: '8px',
              padding: '10px',
              borderRadius: '12px',
              border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              color: isDark ? 'white' : '#1e293b',
              fontSize: '0.9rem',
              fontWeight: 500,
              fontFamily: 'inherit',
            }}>
            <svg width="20" height="20" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
              <path d="M80 55c0-16.6-13.4-30-30-30-12.7 0-23.6 7.9-28 19C13.4 44 6 51.4 6 61c0 11 9 20 20 20h54c8.8 0 16-7.2 16-16 0-7.3-5-13.5-12-15.3C83.3 48 80 51.2 80 55z" fill="#2196F3"/>
              <circle cx="50" cy="42" r="8" fill="white"/>
              <path d="M38 62c0-6.6 5.4-12 12-12s12 5.4 12 12" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round"/>
            </svg>
            Log in with ClassLink
          </button>

          {/* Clever SSO */}
          <button onClick={async () => {
            setError('');
            try {
              const resp = await fetch('/api/clever/login-url');
              const data = await resp.json();
              if (data.url) {
                window.location.href = data.url;
              } else {
                setError('Clever login not configured for this server');
              }
            } catch (err) {
              setError('Could not connect to Clever');
            }
          }}
            style={{
              width: '100%',
              marginTop: '8px',
              padding: '10px',
              borderRadius: '12px',
              border: '1px solid ' + (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'),
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              color: isDark ? 'white' : '#1e293b',
              fontSize: '0.9rem',
              fontWeight: 500,
              fontFamily: 'inherit',
            }}>
            <svg width="18" height="18" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="56" height="56" rx="14" fill="#4274F6"/>
              <path d="M32.8 16.4C29.2 14.3 24.6 14.5 21.2 17C17.8 19.5 16.2 23.7 17 27.8C17.8 31.9 20.8 35.1 24.8 36.2C28.8 37.3 33 35.9 35.6 32.8" stroke="white" strokeWidth="4.5" strokeLinecap="round"/>
            </svg>
            Log in with Clever
          </button>
          </>
  );
}
