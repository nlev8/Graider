/**
 * PasswordResetScreen — branded screen for setting a new password after
 * the user clicks a Supabase recovery email link.
 *
 * Extracted from App.jsx (2026-05-02) — was a top-level function with
 * one call site (App.jsx:5374). Self-contained: only depends on supabase
 * auth client + React useState.
 *
 * Props:
 *   onDone: () => void — invoked after successful password update,
 *           triggers caller's transition out of reset flow.
 */
import React, { useState } from "react";
import { supabase } from "../services/supabase";

export default function PasswordResetScreen({ onDone }) {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (newPassword.length < 6) { setError('Password must be at least 6 characters'); return; }
    if (newPassword !== confirmPassword) { setError('Passwords do not match'); return; }
    setLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password: newPassword });
    setLoading(false);
    if (updateError) { setError(updateError.message); return; }
    setSuccess(true);
  }

  const inputStyle = {
    width: '100%', padding: '12px 16px', borderRadius: 12,
    border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)',
    color: 'white', fontSize: '0.95rem', outline: 'none', boxSizing: 'border-box',
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)', padding: 20,
    }}>
      <div style={{
        width: '100%', maxWidth: 400, background: 'rgba(255,255,255,0.03)',
        backdropFilter: 'blur(20px)', borderRadius: 20,
        border: '1px solid rgba(255,255,255,0.1)', padding: 40,
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{
            fontSize: '2rem', fontWeight: 800,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: 8,
          }}>Graider</h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.95rem' }}>Set your new password</p>
        </div>
        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 12, padding: '12px 16px', marginBottom: 20, color: '#f87171', fontSize: '0.9rem',
          }}>{error}</div>
        )}
        {success ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 12 }}>{String.fromCodePoint(0x2705)}</div>
            <p style={{ color: '#4ade80', marginBottom: 16, fontSize: '1.05rem', fontWeight: 600 }}>
              Password updated successfully!
            </p>
            <button onClick={onDone} style={{
              width: '100%', padding: 14, borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: 'white', cursor: 'pointer', fontSize: '1rem', fontWeight: 600,
            }}>Continue to App</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: 8 }}>New Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showNew ? 'text' : 'password'} value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password" required minLength={6} style={{ ...inputStyle, paddingRight: 44 }} />
                <button type="button" onClick={() => setShowNew(!showNew)}
                  style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'rgba(255,255,255,0.4)', fontSize: '1.1rem', lineHeight: 1 }}
                  aria-label="Toggle password visibility"
                >{showNew ? String.fromCodePoint(0x1F441) : String.fromCodePoint(0x1F441, 0x200D, 0x1F5E8)}</button>
              </div>
            </div>
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: 8 }}>Confirm Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showConfirm ? 'text' : 'password'} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password" required minLength={6} style={{ ...inputStyle, paddingRight: 44 }} />
                <button type="button" onClick={() => setShowConfirm(!showConfirm)}
                  style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'rgba(255,255,255,0.4)', fontSize: '1.1rem', lineHeight: 1 }}
                  aria-label="Toggle password visibility"
                >{showConfirm ? String.fromCodePoint(0x1F441) : String.fromCodePoint(0x1F441, 0x200D, 0x1F5E8)}</button>
              </div>
            </div>
            <button type="submit" disabled={loading} style={{
              width: '100%', padding: 14, borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: 'white', cursor: loading ? 'wait' : 'pointer',
              fontSize: '1rem', fontWeight: 600, opacity: loading ? 0.7 : 1,
            }}>{loading ? 'Updating...' : 'Set New Password'}</button>
          </form>
        )}
      </div>
    </div>
  );
}
