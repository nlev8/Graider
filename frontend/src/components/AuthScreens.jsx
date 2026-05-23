import React from "react";

export function AuthLoadingScreen() {
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

export function ApprovalPendingScreen() {
  return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 16,
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      }}>
        <div className="spin" style={{ width: 40, height: 40, border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#6366f1', borderRadius: '50%' }} />
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14 }}>Checking account status...</p>
      </div>
  );
}

export function NotApprovedScreen({ handleLogout }) {
  return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        color: '#fff',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}>
        <div style={{
          textAlign: 'center',
          maxWidth: 440,
          padding: '48px 32px',
          background: 'rgba(255,255,255,0.05)',
          borderRadius: 16,
          border: '1px solid rgba(255,255,255,0.1)',
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>{String.fromCodePoint(0x23F3)}</div>
          <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Account Pending Approval</h2>
          <p style={{ color: 'rgba(255,255,255,0.6)', lineHeight: 1.6, marginBottom: 28 }}>
            {"Your account has been created successfully. An administrator will review and approve your access shortly. You'll receive an email once approved."}
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '10px 24px',
                borderRadius: 8,
                border: 'none',
                background: '#6366f1',
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: 14,
              }}
            >Check Again</button>
            <button
              onClick={handleLogout}
              style={{
                padding: '10px 24px',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'transparent',
                color: 'rgba(255,255,255,0.7)',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: 14,
              }}
            >Sign Out</button>
          </div>
        </div>
      </div>
  );
}
